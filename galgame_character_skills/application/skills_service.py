import json
import os

from ..utils.tool_handler import ToolHandler
from ..utils.checkpoint_utils import load_resumable_checkpoint
from ..utils.summary_discovery import find_role_summary_markdown_files
from ..utils.request_config import build_llm_config
from ..utils.skills_postprocess import append_vndb_info_to_skill_md, create_code_skill_copy
from ..utils.skills_context_builder import (
    build_full_skill_generation_context,
    build_prioritized_skill_generation_context,
)
from ..utils.compression_service import compress_summary_files_with_llm
from ..utils.llm_budget import get_model_context_limit, calculate_compression_threshold
from ..domain import GenerateSkillsRequest


def run_generate_skills_task(
    data,
    runtime
):
    request_data = GenerateSkillsRequest.from_payload(data, runtime.clean_vndb_data)
    config = build_llm_config(data)

    if request_data.resume_checkpoint_id:
        ckpt, error = load_resumable_checkpoint(runtime.ckpt_manager, request_data.resume_checkpoint_id)
        if error:
            return error

        request_data.apply_checkpoint(ckpt['input_params'])
        checkpoint_id = request_data.resume_checkpoint_id

        llm_state = runtime.ckpt_manager.load_llm_state(checkpoint_id)
        messages = llm_state.get('messages', [])
        all_results = llm_state.get('all_results', [])
        iteration = llm_state.get('iteration_count', 0)
        tools = None

        print(f"Resuming generate_skills: iteration {iteration}, {len(all_results)} results so far")
    else:
        checkpoint_id = runtime.ckpt_manager.create_checkpoint(
            task_type='generate_skills',
            input_params=request_data.to_checkpoint_input()
        )
        messages = []
        all_results = []
        iteration = 0

    script_dir = runtime.get_base_dir()
    summary_files = find_role_summary_markdown_files(script_dir, request_data.role_name)
    if not summary_files:
        return {'success': False, 'message': f'未找到角色 "{request_data.role_name}" 的归纳文件，请先完成归纳'}
    raw_full_text = build_full_skill_generation_context(summary_files)
    raw_total_chars = len(raw_full_text)
    raw_estimated_tokens = runtime.estimate_tokens(raw_full_text)
    context_limit = get_model_context_limit(request_data.model_name)
    context_limit_tokens = calculate_compression_threshold(context_limit)
    target_budget_tokens = context_limit_tokens

    print(f"Model: {request_data.model_name}, Context limit: {context_limit}, Threshold: {context_limit_tokens}")
    print(f"Compression mode: {request_data.compression_mode}, Force no compression: {request_data.force_no_compression}, Raw tokens: {raw_estimated_tokens}, Limit: {context_limit_tokens}")

    if not request_data.force_no_compression and raw_estimated_tokens > context_limit_tokens:
        if request_data.compression_mode == 'llm':
            print("Using LLM compression")
            llm_interaction = runtime.build_llm_client(config)
            summaries_text = compress_summary_files_with_llm(
                summary_files=summary_files,
                llm_client=llm_interaction,
                target_budget_tokens=target_budget_tokens,
                checkpoint_id=checkpoint_id,
                ckpt_manager=runtime.ckpt_manager,
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
        if request_data.force_no_compression and raw_estimated_tokens > context_limit_tokens:
            context_mode = "full_forced"
            print("Force no compression enabled, using full context despite exceeding limit")
        else:
            context_mode = "full"

    if not summaries_text:
        return {'success': False, 'message': f'未能读取角色 "{request_data.role_name}" 的归纳内容'}
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
    llm_interaction = runtime.build_llm_client(config)

    if not request_data.resume_checkpoint_id:
        messages, tools = llm_interaction.generate_skills_folder_init(
            summaries_text,
            request_data.role_name,
            request_data.output_language,
            request_data.vndb_data
        )
        runtime.ckpt_manager.update_progress(checkpoint_id, total_steps=20, current_phase='tool_call_loop')
    else:
        _, tools = llm_interaction.generate_skills_folder_init(
            summaries_text,
            request_data.role_name,
            request_data.output_language,
            request_data.vndb_data
        )

    max_iterations = 20
    while iteration < max_iterations:
        iteration += 1
        runtime.ckpt_manager.save_llm_state(
            checkpoint_id, messages=messages,
            iteration_count=iteration, all_results=all_results
        )
        response = llm_interaction.send_message(messages, tools, use_counter=False)
        if not response:
            runtime.ckpt_manager.save_llm_state(
                checkpoint_id, messages=messages,
                last_response=None, iteration_count=iteration, all_results=all_results
            )
            runtime.ckpt_manager.mark_failed(checkpoint_id, 'LLM交互失败')
            return {
                'success': False, 'message': 'LLM交互失败',
                'checkpoint_id': checkpoint_id, 'can_resume': True
            }
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
                    "arguments": tc.function.arguments
                }
            } for tc in tool_calls]
        }
        messages.append(assistant_message)
        for tool_call in tool_calls:
            result = ToolHandler.handle_tool_call(tool_call)
            all_results.append(result)
            tool_response = {
                "role": "tool",
                "tool_call_id": tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
                "content": json.dumps({"success": True, "result": result})
            }
            messages.append(tool_response)
        runtime.ckpt_manager.save_llm_state(
            checkpoint_id, messages=messages,
            last_response=response, iteration_count=iteration, all_results=all_results
        )
    script_dir = runtime.get_base_dir()
    main_skill_dir = os.path.join(script_dir, f"{request_data.role_name}-skill-main")
    skill_md_path = os.path.join(main_skill_dir, "SKILL.md")
    vndb_result = append_vndb_info_to_skill_md(skill_md_path, request_data.vndb_data)
    if vndb_result:
        all_results.append(vndb_result)
    copy_result = create_code_skill_copy(script_dir, request_data.role_name)
    if copy_result:
        all_results.append(copy_result)
    runtime.ckpt_manager.mark_completed(checkpoint_id)
    return {
        'success': True,
        'message': f'技能文件夹生成完成，共执行 {len(all_results)} 次文件写入',
        'results': all_results,
        'checkpoint_id': checkpoint_id
    }
