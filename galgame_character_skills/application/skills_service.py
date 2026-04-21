import json
import os

from ..checkpoint import load_resumable_checkpoint
from .compression_policy import resolve_compression_policy
from .compression_executor import run_compression_pipeline
from .task_prepared import PreparedGenerateSkillsTask
from .task_state import SkillsResumeState, build_initial_state_factory, build_resume_state_loader
from .task_result_factory import ok_task_result, fail_task_result
from .tool_loop_runner import ToolLoopRunState, run_checkpointed_tool_loop
from .task_prepare_context import (
    build_on_resumed_logger,
    build_clean_payload_loader,
    build_prepared_state_builder,
    prepare_task_context,
)
from ..files import find_role_summary_markdown_files
from ..utils.request_config import build_llm_config
from ..skills import (
    append_vndb_info_to_skill_md,
    create_code_skill_copy,
    build_full_skill_generation_context,
    build_prioritized_skill_generation_context,
)
from ..utils.compression_service import compress_summary_files_with_llm
from ..domain import GenerateSkillsRequest, fail_result
from ..workspace import get_workspace_skills_dir, get_workspace_summaries_dir


_load_resume_skills_state = build_resume_state_loader(
    SkillsResumeState,
    {
        "messages": "messages",
        "all_results": "all_results",
        "iteration": "iteration_count",
    },
)
_build_initial_skills_state = build_initial_state_factory(SkillsResumeState)
_from_skills_payload = build_clean_payload_loader(GenerateSkillsRequest)
_build_prepared_skills_task = build_prepared_state_builder(
    PreparedGenerateSkillsTask,
    ("messages", "all_results", "iteration"),
)
_on_skills_resumed = build_on_resumed_logger(
    lambda _request_data, checkpoint_data, _runtime: (
        f"Resuming generate_skills: iteration {checkpoint_data.state.iteration}, "
        f"{len(checkpoint_data.state.all_results)} results so far"
    )
)


def _prepare_generate_skills_request(data, runtime):
    return prepare_task_context(
        data=data,
        runtime=runtime,
        from_payload=_from_skills_payload,
        config_builder=build_llm_config,
        checkpoint_task_type="generate_skills",
        load_resume_state=_load_resume_skills_state,
        build_initial_state=_build_initial_skills_state,
        load_resumable_checkpoint_fn=load_resumable_checkpoint,
        build_prepared=_build_prepared_skills_task,
        on_resumed=_on_skills_resumed,
    )


def _build_skill_context(summary_files, request_data, config, checkpoint_id, runtime):
    raw_full_text = build_full_skill_generation_context(summary_files)
    raw_total_chars = len(raw_full_text)
    raw_estimated_tokens = runtime.estimate_tokens(raw_full_text)
    policy = resolve_compression_policy(
        model_name=request_data.model_name,
        raw_estimated_tokens=raw_estimated_tokens,
        force_no_compression=request_data.force_no_compression,
    )
    context_mode = "full"
    summaries_text = raw_full_text

    def _llm_compress(target_budget_tokens):
        print("Using LLM compression")
        llm_interaction = runtime.llm_gateway.create_client(config)
        return compress_summary_files_with_llm(
            summary_files=summary_files,
            llm_client=llm_interaction,
            target_budget_tokens=target_budget_tokens,
            checkpoint_id=checkpoint_id,
            ckpt_manager=runtime.checkpoint_gateway,
            estimate_tokens=runtime.estimate_tokens,
        )

    def _fallback_compress(target_budget_tokens):
        print("Using original compression")
        target_budget_chars = target_budget_tokens * 2
        return build_prioritized_skill_generation_context(
            summary_files,
            target_total_chars=target_budget_chars,
        )

    compressed, used_compression, context_limit, context_limit_tokens = run_compression_pipeline(
        runtime=runtime,
        model_name=request_data.model_name,
        compression_mode=request_data.compression_mode,
        force_no_compression=request_data.force_no_compression,
        raw_estimated_tokens=raw_estimated_tokens,
        policy=policy,
        llm_compress=_llm_compress,
        fallback_compress=_fallback_compress,
    )
    if used_compression:
        summaries_text = compressed
        context_mode = "llm_compressed" if request_data.compression_mode == "llm" else "compressed"
    elif policy["force_exceeds_limit"]:
        context_mode = "full_forced"

    if not summaries_text:
        return None, fail_result(f'未能读取角色 "{request_data.role_name}" 的归纳内容')

    compressed_chars = len(summaries_text)
    estimated_tokens = runtime.estimate_tokens(summaries_text)
    compression_ratio = (compressed_chars / raw_total_chars) if raw_total_chars else 0
    strategy_name = {
        'full': 'full_context',
        'full_forced': 'full_context_no_compression',
        'compressed': 'head_tail_weighted_1_2_then_key_sections',
        'llm_compressed': 'llm_deduplication'
    }.get(context_mode, 'unknown')

    print(
        f"role={request_data.role_name} files={len(summary_files)} mode={context_mode} "
        f"raw_chars={raw_total_chars} raw_estimated_tokens={raw_estimated_tokens} "
        f"final_chars={compressed_chars} final_estimated_tokens={estimated_tokens} "
        f"compression_ratio={compression_ratio:.2%} "
        f"strategy={strategy_name}"
    )

    return {
        'summaries_text': summaries_text,
        'context_mode': context_mode,
    }, None


def _initialize_skill_generation(llm_interaction, summaries_text, request_data, resume_checkpoint_id, output_root_dir):
    if not resume_checkpoint_id:
        messages, tools = llm_interaction.generate_skills_folder_init(
            summaries_text,
            request_data.role_name,
            request_data.output_language,
            request_data.vndb_data,
            output_root_dir=output_root_dir,
        )
    else:
        _, tools = llm_interaction.generate_skills_folder_init(
            summaries_text,
            request_data.role_name,
            request_data.output_language,
            request_data.vndb_data,
            output_root_dir=output_root_dir,
        )
        messages = None

    return messages, tools


def _run_tool_call_loop(messages, tools, all_results, iteration, checkpoint_id, llm_interaction, runtime):
    def _append_tool_exchange(response, tool_calls, messages_ref, all_results_ref):
        assistant_message = {
            "role": "assistant",
            "content": response.choices[0].message.content if response.choices[0].message.content else "",
            "tool_calls": [tc if isinstance(tc, dict) else {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
            } for tc in tool_calls]
        }
        messages_ref.append(assistant_message)

        for tool_call in tool_calls:
            result = runtime.tool_gateway.handle_tool_call(tool_call)
            all_results_ref.append(result)
            tool_response = {
                "role": "tool",
                "tool_call_id": tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
                "content": json.dumps({"success": True, "result": result})
            }
            messages_ref.append(tool_response)

    def _on_send_failed(message):
        runtime.checkpoint_gateway.mark_failed(checkpoint_id, message)
        return fail_task_result(message, checkpoint_id=checkpoint_id, can_resume=True)

    state, error = run_checkpointed_tool_loop(
        messages=messages,
        tools=tools,
        all_results=all_results,
        iteration=iteration,
        max_iterations=20,
        checkpoint_gateway=runtime.checkpoint_gateway,
        checkpoint_id=checkpoint_id,
        send_message=lambda msgs, tool_defs: llm_interaction.send_message(msgs, tool_defs, use_counter=False),
        get_tool_calls=llm_interaction.get_tool_response,
        append_tool_exchange=_append_tool_exchange,
        on_send_failed=_on_send_failed,
        failure_message="LLM交互失败",
    )
    if error:
        return None, error

    return ToolLoopRunState(
        messages=state.messages,
        all_results=state.all_results,
        iteration=state.iteration,
    ), None


def _finalize_generate_skills(request_data, checkpoint_id, all_results, runtime):
    skills_root_dir = get_workspace_skills_dir()
    runtime.storage_gateway.makedirs(skills_root_dir, exist_ok=True)
    main_skill_dir = os.path.join(skills_root_dir, f"{request_data.role_name}-skill-main")
    skill_md_path = os.path.join(main_skill_dir, "SKILL.md")

    vndb_result = append_vndb_info_to_skill_md(skill_md_path, request_data.vndb_data)
    if vndb_result:
        all_results.append(vndb_result)

    copy_result = create_code_skill_copy(skills_root_dir, request_data.role_name)
    if copy_result:
        all_results.append(copy_result)

    runtime.checkpoint_gateway.mark_completed(checkpoint_id)
    return ok_task_result(
        message=f'技能文件夹生成完成，共执行 {len(all_results)} 次文件写入',
        results=all_results,
        checkpoint_id=checkpoint_id,
    )


def run_generate_skills_task(
    data,
    runtime
):
    prepared, error = _prepare_generate_skills_request(data, runtime)
    if error:
        return error

    request_data = prepared.request_data
    config = prepared.config
    checkpoint_id = prepared.checkpoint_id
    messages = prepared.messages
    all_results = prepared.all_results
    iteration = prepared.iteration

    summaries_root_dir = get_workspace_summaries_dir()
    summary_files = find_role_summary_markdown_files(summaries_root_dir, request_data.role_name)
    if not summary_files:
        return fail_result(f'未找到角色 "{request_data.role_name}" 的归纳文件，请先完成归纳')

    skills_root_dir = get_workspace_skills_dir()
    runtime.storage_gateway.makedirs(skills_root_dir, exist_ok=True)
    prompt_skills_root_dir = skills_root_dir.replace("\\", "/")

    context_data, error = _build_skill_context(
        summary_files=summary_files,
        request_data=request_data,
        config=config,
        checkpoint_id=checkpoint_id,
        runtime=runtime,
    )
    if error:
        return error

    llm_interaction = runtime.llm_gateway.create_client(config)
    init_messages, tools = _initialize_skill_generation(
        llm_interaction=llm_interaction,
        summaries_text=context_data['summaries_text'],
        request_data=request_data,
        resume_checkpoint_id=request_data.resume_checkpoint_id,
        output_root_dir=prompt_skills_root_dir,
    )

    if not request_data.resume_checkpoint_id:
        messages = init_messages
        runtime.checkpoint_gateway.update_progress(checkpoint_id, total_steps=20, current_phase='tool_call_loop')

    loop_result, error = _run_tool_call_loop(
        messages=messages,
        tools=tools,
        all_results=all_results,
        iteration=iteration,
        checkpoint_id=checkpoint_id,
        llm_interaction=llm_interaction,
        runtime=runtime,
    )
    if error:
        return error

    return _finalize_generate_skills(
        request_data=request_data,
        checkpoint_id=checkpoint_id,
        all_results=loop_result.all_results,
        runtime=runtime,
    )
