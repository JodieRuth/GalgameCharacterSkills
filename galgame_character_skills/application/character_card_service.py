import json
import os

from ..utils.checkpoint_utils import load_resumable_checkpoint
from ..utils.summary_discovery import find_role_analysis_summary_file
from ..utils.request_config import build_llm_config
from ..utils.llm_budget import get_model_context_limit, calculate_compression_threshold
from ..utils.compression_service import compress_analyses_with_llm
from ..domain import GenerateCharacterCardRequest, ok_result, fail_result


def run_generate_character_card_task(
    data,
    runtime
):
    request_data = GenerateCharacterCardRequest.from_payload(data, runtime.clean_vndb_data)
    config = build_llm_config(data)

    if request_data.resume_checkpoint_id:
        ckpt_result = load_resumable_checkpoint(runtime.checkpoint_gateway, request_data.resume_checkpoint_id)
        if not ckpt_result.get('success'):
            return ckpt_result
        ckpt = ckpt_result['checkpoint']

        request_data.apply_checkpoint(ckpt['input_params'])
        checkpoint_id = request_data.resume_checkpoint_id

        llm_state = runtime.checkpoint_gateway.load_llm_state(checkpoint_id)
        fields_data = llm_state.get('fields_data', {})
        messages = llm_state.get('messages', [])
        iteration_count = llm_state.get('iteration_count', 0)

        print(f"Resuming generate_chara_card: iteration {iteration_count}, fields: {list(fields_data.keys())}")
    else:
        checkpoint_id = runtime.checkpoint_gateway.create_checkpoint(
            task_type='generate_chara_card',
            input_params=request_data.to_checkpoint_input()
        )
        fields_data = {}
        messages = []
        iteration_count = 0

    script_dir = runtime.get_base_dir()
    analysis_file = find_role_analysis_summary_file(script_dir, request_data.role_name)

    if not analysis_file:
        return fail_result(f'未找到角色 "{request_data.role_name}" 的分析文件，请先完成归纳')

    try:
        analysis_data = runtime.storage_gateway.read_json(analysis_file)
    except Exception as e:
        return fail_result(f'读取分析文件失败: {str(e)}')

    all_character_analyses = analysis_data.get('character_analyses', [])
    all_lorebook_entries = analysis_data.get('lorebook_entries', [])

    if not all_character_analyses:
        return fail_result('分析数据为空')

    analyses_text = json.dumps(all_character_analyses, ensure_ascii=False)
    raw_estimated_tokens = runtime.estimate_tokens(analyses_text)
    context_limit = get_model_context_limit(request_data.model_name)
    context_limit_tokens = calculate_compression_threshold(context_limit)
    target_budget_tokens = context_limit_tokens

    print(f"Model: {request_data.model_name}, Context limit: {context_limit}, Threshold: {context_limit_tokens}")
    print(f"Compression mode: {request_data.compression_mode}, Force no compression: {request_data.force_no_compression}, Raw tokens: {raw_estimated_tokens}, Limit: {context_limit_tokens}")

    if not request_data.force_no_compression and raw_estimated_tokens > context_limit_tokens:
        if request_data.compression_mode == 'llm':
            print("Using LLM compression for analyses")
            llm_interaction = runtime.llm_gateway.create_client(config)
            compressed_analyses = compress_analyses_with_llm(
                analyses=all_character_analyses,
                llm_client=llm_interaction,
                target_budget_tokens=target_budget_tokens,
                checkpoint_id=checkpoint_id,
                ckpt_manager=runtime.checkpoint_gateway,
                estimate_tokens=runtime.estimate_tokens
            )
            all_character_analyses = compressed_analyses
            context_mode = "llm_compressed"
        else:
            print("Using original compression")
            target_count = max(1, len(all_character_analyses) * target_budget_tokens // raw_estimated_tokens)
            all_character_analyses = all_character_analyses[:target_count]
            context_mode = "compressed"

        compressed_text = json.dumps(all_character_analyses, ensure_ascii=False)
        compressed_tokens = runtime.estimate_tokens(compressed_text)
        print(f"Compressed: {raw_estimated_tokens} -> {compressed_tokens} tokens ({compressed_tokens/raw_estimated_tokens*100:.1f}%)")
    else:
        if request_data.force_no_compression and raw_estimated_tokens > context_limit_tokens:
            context_mode = "full_forced"
            print("Force no compression enabled, using full context despite exceeding limit")
        else:
            context_mode = "full"
        print(f"No compression needed ({raw_estimated_tokens} <= {context_limit_tokens})")

    output_dir = os.path.join(script_dir, f"{request_data.role_name}-character-card")
    runtime.storage_gateway.makedirs(output_dir, exist_ok=True)
    json_output_path = os.path.join(output_dir, f"{request_data.role_name}_chara_card.json")

    image_path = None
    if request_data.vndb_data_raw and request_data.vndb_data_raw.get('image_url'):
        image_ext = os.path.splitext(request_data.vndb_data_raw['image_url'])[1] or '.jpg'
        ckpt_temp_dir = runtime.checkpoint_gateway.get_temp_dir(checkpoint_id)
        image_path = os.path.join(ckpt_temp_dir, f"{request_data.role_name}_vndb{image_ext}")
        if runtime.storage_gateway.exists(image_path):
            print(f"VNDB image already exists: {image_path}")
        elif runtime.download_vndb_image(request_data.vndb_data_raw['image_url'], image_path):
            print(f"Downloaded VNDB image to: {image_path}")
        else:
            image_path = None

    llm_interaction = runtime.llm_gateway.create_client(config)
    result = llm_interaction.generate_character_card_with_tools(
        request_data.role_name,
        all_character_analyses,
        all_lorebook_entries,
        json_output_path,
        request_data.creator,
        request_data.vndb_data,
        request_data.output_language,
        checkpoint_id=checkpoint_id,
        ckpt_messages=messages if request_data.resume_checkpoint_id else None,
        ckpt_fields_data=fields_data if request_data.resume_checkpoint_id else None,
        ckpt_iteration_count=iteration_count if request_data.resume_checkpoint_id else None
    )

    if result.get('success'):
        runtime.checkpoint_gateway.mark_completed(checkpoint_id, final_output_path=json_output_path)
        try:
            chara_card_json = runtime.storage_gateway.read_json(json_output_path)
        except Exception as e:
            return ok_result(
                message=f'角色卡生成完成 (JSON): {json_output_path}',
                output_path=json_output_path,
                fields_written=result.get('fields_written', []),
                image_path=image_path,
                warning=f'无法读取JSON用于PNG嵌入: {str(e)}',
                checkpoint_id=checkpoint_id
            )

        png_output_path = None
        conversion_error = None
        if image_path and runtime.storage_gateway.exists(image_path):
            png_output_path = os.path.join(output_dir, f"{request_data.role_name}_chara_card.png")

            if image_path.lower().endswith('.png'):
                if runtime.embed_json_in_png(chara_card_json, image_path, png_output_path):
                    print(f"Created PNG character card: {png_output_path}")
                else:
                    png_output_path = None
                    conversion_error = "Failed to embed JSON in PNG"
            else:
                try:
                    from PIL import Image
                    img = Image.open(image_path)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        if img.mode in ('RGBA', 'LA'):
                            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                            img = background
                    else:
                        img = img.convert('RGB')
                    temp_png = os.path.join(runtime.checkpoint_gateway.get_temp_dir(checkpoint_id), f"{request_data.role_name}_temp.png")
                    img.save(temp_png, 'PNG', optimize=True)
                    print(f"Converted image to PNG: {temp_png}")
                    if runtime.embed_json_in_png(chara_card_json, temp_png, png_output_path):
                        print(f"Created PNG character card with embedded JSON: {png_output_path}")
                    else:
                        png_output_path = None
                        conversion_error = "Failed to embed JSON in converted PNG"
                    if runtime.storage_gateway.exists(temp_png):
                        runtime.storage_gateway.remove_file(temp_png)
                except ImportError:
                    conversion_error = "PIL (Pillow) not installed. Run: pip install Pillow"
                    print(conversion_error)
                    png_output_path = None
                except Exception as e:
                    conversion_error = f"Image conversion failed: {str(e)}"
                    print(conversion_error)
                    png_output_path = None

            if image_path and runtime.storage_gateway.exists(image_path) and not request_data.resume_checkpoint_id:
                try:
                    runtime.storage_gateway.remove_file(image_path)
                    print(f"Cleaned up VNDB image: {image_path}")
                    image_path = None
                except Exception as e:
                    print(f"Failed to clean up VNDB image: {e}")

        response_data = ok_result(
            message=f'角色卡生成完成: {json_output_path}',
            output_path=json_output_path,
            fields_written=result.get('fields_written', []),
            result=result.get('result', ''),
            checkpoint_id=checkpoint_id
        )

        if image_path:
            response_data['image_path'] = image_path
        if png_output_path:
            response_data['png_path'] = png_output_path
        if conversion_error:
            response_data['conversion_error'] = conversion_error

        return response_data

    if result.get('can_resume'):
        runtime.checkpoint_gateway.mark_failed(checkpoint_id, result.get('message', '生成失败'))
        return fail_result(
            result.get('message', '生成失败'),
            checkpoint_id=checkpoint_id,
            can_resume=True
        )
    return fail_result(result.get('message', '生成失败'))
