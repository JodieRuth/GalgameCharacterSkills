import json
import os

from ..checkpoint import load_resumable_checkpoint
from .checkpoint_prepare import prepare_request_with_checkpoint
from .compression_policy import resolve_compression_policy
from ..files import find_role_summary_markdown_files
from ..utils.request_config import build_llm_config
from ..skills import (
    append_vndb_info_to_skill_md,
    create_code_skill_copy,
    build_full_skill_generation_context,
    build_prioritized_skill_generation_context,
)
from ..utils.compression_service import compress_summary_files_with_llm
from ..domain import GenerateSkillsRequest, ok_result, fail_result
from ..workspace import get_workspace_skills_dir, get_workspace_summaries_dir


def _load_resume_skills_state(checkpoint_gateway, checkpoint_id, _checkpoint):
    llm_state = checkpoint_gateway.load_llm_state(checkpoint_id)
    return {
        "messages": llm_state.get("messages", []),
        "all_results": llm_state.get("all_results", []),
        "iteration": llm_state.get("iteration_count", 0),
    }


def _build_initial_skills_state():
    return {
        "messages": [],
        "all_results": [],
        "iteration": 0,
    }


def _prepare_generate_skills_request(data, runtime):
    request_data = GenerateSkillsRequest.from_payload(data, runtime.clean_vndb_data)
    config = build_llm_config(data)
    checkpoint_data, error = prepare_request_with_checkpoint(
        request_data=request_data,
        checkpoint_gateway=runtime.checkpoint_gateway,
        task_type="generate_skills",
        load_resume_state=_load_resume_skills_state,
        build_initial_state=_build_initial_skills_state,
        load_resumable_checkpoint_fn=load_resumable_checkpoint,
    )
    if error:
        return None, error
    checkpoint_id = checkpoint_data["checkpoint_id"]
    state = checkpoint_data["state"]
    messages = state["messages"]
    all_results = state["all_results"]
    iteration = state["iteration"]

    if checkpoint_data["resumed"]:
        print(f"Resuming generate_skills: iteration {iteration}, {len(all_results)} results so far")

    return {
        'request_data': request_data,
        'config': config,
        'checkpoint_id': checkpoint_id,
        'messages': messages,
        'all_results': all_results,
        'iteration': iteration,
    }, None


def _build_skill_context(summary_files, request_data, config, checkpoint_id, runtime):
    raw_full_text = build_full_skill_generation_context(summary_files)
    raw_total_chars = len(raw_full_text)
    raw_estimated_tokens = runtime.estimate_tokens(raw_full_text)
    policy = resolve_compression_policy(
        model_name=request_data.model_name,
        raw_estimated_tokens=raw_estimated_tokens,
        force_no_compression=request_data.force_no_compression,
    )
    context_limit = policy["context_limit"]
    context_limit_tokens = policy["context_limit_tokens"]
    target_budget_tokens = context_limit_tokens

    print(f"Model: {request_data.model_name}, Context limit: {context_limit}, Threshold: {context_limit_tokens}")
    print(f"Compression mode: {request_data.compression_mode}, Force no compression: {request_data.force_no_compression}, Raw tokens: {raw_estimated_tokens}, Limit: {context_limit_tokens}")

    if policy["should_compress"]:
        if request_data.compression_mode == 'llm':
            print("Using LLM compression")
            llm_interaction = runtime.llm_gateway.create_client(config)
            summaries_text = compress_summary_files_with_llm(
                summary_files=summary_files,
                llm_client=llm_interaction,
                target_budget_tokens=target_budget_tokens,
                checkpoint_id=checkpoint_id,
                ckpt_manager=runtime.checkpoint_gateway,
                estimate_tokens=runtime.estimate_tokens
            )
            context_mode = "llm_compressed"
        else:
            print("Using original compression")
            target_budget_chars = target_budget_tokens * 2
            summaries_text = build_prioritized_skill_generation_context(
                summary_files,
                target_total_chars=target_budget_chars
            )
            context_mode = "compressed"
    else:
        summaries_text = raw_full_text
        if policy["force_exceeds_limit"]:
            context_mode = "full_forced"
            print("Force no compression enabled, using full context despite exceeding limit")
        else:
            context_mode = "full"

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
    max_iterations = 20

    while iteration < max_iterations:
        iteration += 1
        runtime.checkpoint_gateway.save_llm_state(
            checkpoint_id,
            messages=messages,
            iteration_count=iteration,
            all_results=all_results,
        )
        response = llm_interaction.send_message(messages, tools, use_counter=False)
        if not response:
            runtime.checkpoint_gateway.save_llm_state(
                checkpoint_id,
                messages=messages,
                last_response=None,
                iteration_count=iteration,
                all_results=all_results,
            )
            runtime.checkpoint_gateway.mark_failed(checkpoint_id, 'LLM交互失败')
            return None, fail_result(
                'LLM交互失败',
                checkpoint_id=checkpoint_id,
                can_resume=True,
            )

        tool_calls = llm_interaction.get_tool_response(response)
        if not tool_calls:
            break

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
        messages.append(assistant_message)

        for tool_call in tool_calls:
            result = runtime.tool_gateway.handle_tool_call(tool_call)
            all_results.append(result)
            tool_response = {
                "role": "tool",
                "tool_call_id": tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
                "content": json.dumps({"success": True, "result": result})
            }
            messages.append(tool_response)

        runtime.checkpoint_gateway.save_llm_state(
            checkpoint_id,
            messages=messages,
            last_response=response,
            iteration_count=iteration,
            all_results=all_results,
        )

    return {
        'messages': messages,
        'all_results': all_results,
        'iteration': iteration,
    }, None


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
    return ok_result(
        message=f'技能文件夹生成完成，共执行 {len(all_results)} 次文件写入',
        results=all_results,
        checkpoint_id=checkpoint_id
    )


def run_generate_skills_task(
    data,
    runtime
):
    prepared, error = _prepare_generate_skills_request(data, runtime)
    if error:
        return error

    request_data = prepared['request_data']
    config = prepared['config']
    checkpoint_id = prepared['checkpoint_id']
    messages = prepared['messages']
    all_results = prepared['all_results']
    iteration = prepared['iteration']

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
        all_results=loop_result['all_results'],
        runtime=runtime,
    )
