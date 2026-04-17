import json
import os

from utils.tool_handler import ToolHandler
from services.checkpoint_utils import load_resumable_checkpoint
from services.summary_discovery import find_role_summary_markdown_files


def run_generate_skills_task(
    data,
    ckpt_manager,
    clean_vndb_data,
    get_base_dir,
    build_full_context,
    estimate_tokens,
    get_model_context_limit,
    calculate_compression_threshold,
    compress_with_llm,
    build_prioritized_context,
    build_llm_client
):
    role_name = data.get('role_name', '')
    vndb_data = clean_vndb_data(data.get('vndb_data'))
    output_language = data.get('output_language', '')
    compression_mode = data.get('compression_mode', 'original')
    force_no_compression = data.get('force_no_compression', False)
    resume_checkpoint_id = data.get('resume_checkpoint_id')
    config = {
        'baseurl': data.get('baseurl', ''),
        'modelname': data.get('modelname', ''),
        'apikey': data.get('apikey', ''),
        'max_retries': data.get('max_retries', 0) or None
    }

    if resume_checkpoint_id:
        ckpt, error = load_resumable_checkpoint(ckpt_manager, resume_checkpoint_id)
        if error:
            return error

        role_name = ckpt['input_params'].get('role_name', role_name)
        vndb_data = ckpt['input_params'].get('vndb_data', vndb_data)
        output_language = ckpt['input_params'].get('output_language', output_language)
        compression_mode = ckpt['input_params'].get('compression_mode', compression_mode)
        force_no_compression = ckpt['input_params'].get('force_no_compression', force_no_compression)
        checkpoint_id = resume_checkpoint_id

        llm_state = ckpt_manager.load_llm_state(checkpoint_id)
        messages = llm_state.get('messages', [])
        all_results = llm_state.get('all_results', [])
        iteration = llm_state.get('iteration_count', 0)
        tools = None

        print(f"Resuming generate_skills: iteration {iteration}, {len(all_results)} results so far")
    else:
        checkpoint_id = ckpt_manager.create_checkpoint(
            task_type='generate_skills',
            input_params={
                'role_name': role_name,
                'vndb_data': vndb_data,
                'output_language': output_language,
                'compression_mode': compression_mode,
                'force_no_compression': force_no_compression
            }
        )
        messages = []
        all_results = []
        iteration = 0

    script_dir = get_base_dir()
    summary_files = find_role_summary_markdown_files(script_dir, role_name)
    if not summary_files:
        return {'success': False, 'message': f'未找到角色 "{role_name}" 的归纳文件，请先完成归纳'}
    raw_full_text = build_full_context(summary_files)
    raw_total_chars = len(raw_full_text)
    raw_estimated_tokens = estimate_tokens(raw_full_text)
    model_name = data.get('modelname', '')
    context_limit = get_model_context_limit(model_name)
    context_limit_tokens = calculate_compression_threshold(context_limit)
    target_budget_tokens = context_limit_tokens

    print(f"Model: {model_name}, Context limit: {context_limit}, Threshold: {context_limit_tokens}")
    print(f"Compression mode: {compression_mode}, Force no compression: {force_no_compression}, Raw tokens: {raw_estimated_tokens}, Limit: {context_limit_tokens}")

    if not force_no_compression and raw_estimated_tokens > context_limit_tokens:
        if compression_mode == 'llm':
            print("Using LLM compression")
            llm_interaction = build_llm_client(config)
            summaries_text = compress_with_llm(summary_files, llm_interaction, target_budget_tokens, checkpoint_id=checkpoint_id)
            context_mode = "llm_compressed"
        else:
            print("Using original compression")
            target_budget_chars = target_budget_tokens * 2
            summaries_text = build_prioritized_context(
                summary_files,
                target_total_chars=target_budget_chars
            )
            context_mode = "compressed"
    else:
        summaries_text = raw_full_text
        if force_no_compression and raw_estimated_tokens > context_limit_tokens:
            context_mode = "full_forced"
            print("Force no compression enabled, using full context despite exceeding limit")
        else:
            context_mode = "full"

    if not summaries_text:
        return {'success': False, 'message': f'未能读取角色 "{role_name}" 的归纳内容'}
    compressed_chars = len(summaries_text)
    estimated_tokens = estimate_tokens(summaries_text)
    compression_ratio = (compressed_chars / raw_total_chars) if raw_total_chars else 0
    strategy_name = {
        'full': 'full_context',
        'full_forced': 'full_context_no_compression',
        'compressed': 'head_tail_weighted_1_2_then_key_sections',
        'llm_compressed': 'llm_deduplication'
    }.get(context_mode, 'unknown')

    print(
        f"role={role_name} files={len(summary_files)} mode={context_mode} "
        f"raw_chars={raw_total_chars} raw_estimated_tokens={raw_estimated_tokens} "
        f"final_chars={compressed_chars} final_estimated_tokens={estimated_tokens} "
        f"compression_ratio={compression_ratio:.2%} "
        f"strategy={strategy_name}"
    )
    llm_interaction = build_llm_client(config)

    if not resume_checkpoint_id:
        messages, tools = llm_interaction.generate_skills_folder_init(summaries_text, role_name, output_language, vndb_data)
        ckpt_manager.update_progress(checkpoint_id, total_steps=20, current_phase='tool_call_loop')
    else:
        _, tools = llm_interaction.generate_skills_folder_init(summaries_text, role_name, output_language, vndb_data)

    max_iterations = 20
    while iteration < max_iterations:
        iteration += 1
        ckpt_manager.save_llm_state(
            checkpoint_id, messages=messages,
            iteration_count=iteration, all_results=all_results
        )
        response = llm_interaction.send_message(messages, tools, use_counter=False)
        if not response:
            ckpt_manager.save_llm_state(
                checkpoint_id, messages=messages,
                last_response=None, iteration_count=iteration, all_results=all_results
            )
            ckpt_manager.mark_failed(checkpoint_id, 'LLM交互失败')
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
        ckpt_manager.save_llm_state(
            checkpoint_id, messages=messages,
            last_response=response, iteration_count=iteration, all_results=all_results
        )
    try:
        script_dir = get_base_dir()
        main_skill_dir = os.path.join(script_dir, f"{role_name}-skill-main")
        code_skill_dir = os.path.join(script_dir, f"{role_name}-skill-code")

        if vndb_data:
            skill_md_path = os.path.join(main_skill_dir, "SKILL.md")
            if os.path.exists(skill_md_path):
                try:
                    with open(skill_md_path, 'r', encoding='utf-8') as f:
                        skill_content = f.read()

                    vndb_section = "\n\n---\n\n## VNDB Character Information\n\n"
                    if vndb_data.get('name'):
                        vndb_section += f"- **Name**: {vndb_data['name']}\n"
                    if vndb_data.get('original_name'):
                        vndb_section += f"- **Original Name**: {vndb_data['original_name']}\n"
                    if vndb_data.get('aliases'):
                        vndb_section += f"- **Aliases**: {', '.join(vndb_data['aliases'])}\n"
                    if vndb_data.get('description'):
                        vndb_section += f"- **Description**: {vndb_data['description']}\n"
                    if vndb_data.get('age'):
                        vndb_section += f"- **Age**: {vndb_data['age']}\n"
                    if vndb_data.get('birthday'):
                        vndb_section += f"- **Birthday**: {vndb_data['birthday']}\n"
                    if vndb_data.get('blood_type'):
                        vndb_section += f"- **Blood Type**: {vndb_data['blood_type']}\n"
                    if vndb_data.get('height'):
                        vndb_section += f"- **Height**: {vndb_data['height']}cm\n"
                    if vndb_data.get('weight'):
                        vndb_section += f"- **Weight**: {vndb_data['weight']}kg\n"
                    if vndb_data.get('bust') and vndb_data.get('waist') and vndb_data.get('hips'):
                        vndb_section += f"- **Measurements**: {vndb_data['bust']}-{vndb_data['waist']}-{vndb_data['hips']}cm\n"
                    if vndb_data.get('traits'):
                        vndb_section += f"- **Traits**: {', '.join(vndb_data['traits'])}\n"
                    if vndb_data.get('vns'):
                        games = vndb_data['vns'][:3]
                        vndb_section += f"- **Visual Novels**: {', '.join(games)}\n"

                    skill_content += vndb_section

                    with open(skill_md_path, 'w', encoding='utf-8') as f:
                        f.write(skill_content)

                    all_results.append("Added VNDB info to SKILL.md")
                except Exception as e:
                    all_results.append(f"Warning: Failed to add VNDB info to SKILL.md: {e}")

        if os.path.exists(main_skill_dir):
            if os.path.exists(code_skill_dir):
                import shutil
                shutil.rmtree(code_skill_dir)
            import shutil
            shutil.copytree(main_skill_dir, code_skill_dir)
            limit_file = os.path.join(code_skill_dir, "limit.md")
            if os.path.exists(limit_file):
                os.remove(limit_file)
            all_results.append(f"Created {role_name}-skill-code (without limit.md)")
    except Exception as e:
        all_results.append(f"Warning: Failed to create -code version: {e}")
    ckpt_manager.mark_completed(checkpoint_id)
    return {
        'success': True,
        'message': f'技能文件夹生成完成，共执行 {len(all_results)} 次文件写入',
        'results': all_results,
        'checkpoint_id': checkpoint_id
    }
