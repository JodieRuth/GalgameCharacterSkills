import json
import os

from ..checkpoint import load_resumable_checkpoint
from ..files import find_role_analysis_summary_file
from ..utils.request_config import build_llm_config
from ..utils.llm_budget import get_model_context_limit, calculate_compression_threshold
from ..utils.compression_service import compress_analyses_with_llm
from ..domain import GenerateCharacterCardRequest, ok_result, fail_result


def _prepare_generate_character_card_request(data, runtime):
    request_data = GenerateCharacterCardRequest.from_payload(data, runtime.clean_vndb_data)
    config = build_llm_config(data)

    if request_data.resume_checkpoint_id:
        ckpt_result = load_resumable_checkpoint(runtime.checkpoint_gateway, request_data.resume_checkpoint_id)
        if not ckpt_result.get('success'):
            return None, ckpt_result
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

    return {
        'request_data': request_data,
        'config': config,
        'checkpoint_id': checkpoint_id,
        'fields_data': fields_data,
        'messages': messages,
        'iteration_count': iteration_count,
    }, None


def _load_character_analyses(runtime, role_name):
    script_dir = runtime.get_base_dir()
    analysis_file = find_role_analysis_summary_file(script_dir, role_name)

    if not analysis_file:
        return None, None, script_dir, fail_result(f'未找到角色 "{role_name}" 的分析文件，请先完成归纳')

    try:
        analysis_data = runtime.storage_gateway.read_json(analysis_file)
    except Exception as e:
        return None, None, script_dir, fail_result(f'读取分析文件失败: {str(e)}')

    all_character_analyses = analysis_data.get('character_analyses', [])
    all_lorebook_entries = analysis_data.get('lorebook_entries', [])

    if not all_character_analyses:
        return None, None, script_dir, fail_result('分析数据为空')

    return all_character_analyses, all_lorebook_entries, script_dir, None


def _compress_character_analyses(all_character_analyses, request_data, config, checkpoint_id, runtime):
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
            all_character_analyses = compress_analyses_with_llm(
                analyses=all_character_analyses,
                llm_client=llm_interaction,
                target_budget_tokens=target_budget_tokens,
                checkpoint_id=checkpoint_id,
                ckpt_manager=runtime.checkpoint_gateway,
                estimate_tokens=runtime.estimate_tokens
            )
        else:
            print("Using original compression")
            target_count = max(1, len(all_character_analyses) * target_budget_tokens // raw_estimated_tokens)
            all_character_analyses = all_character_analyses[:target_count]

        compressed_text = json.dumps(all_character_analyses, ensure_ascii=False)
        compressed_tokens = runtime.estimate_tokens(compressed_text)
        print(f"Compressed: {raw_estimated_tokens} -> {compressed_tokens} tokens ({compressed_tokens/raw_estimated_tokens*100:.1f}%)")
    else:
        if request_data.force_no_compression and raw_estimated_tokens > context_limit_tokens:
            print("Force no compression enabled, using full context despite exceeding limit")
        else:
            print(f"No compression needed ({raw_estimated_tokens} <= {context_limit_tokens})")

    return all_character_analyses


def _prepare_output_paths(runtime, script_dir, request_data, checkpoint_id):
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

    return {
        'output_dir': output_dir,
        'json_output_path': json_output_path,
        'image_path': image_path,
    }


def _embed_json_to_png(runtime, request_data, checkpoint_id, output_dir, image_path, chara_card_json):
    png_output_path = os.path.join(output_dir, f"{request_data.role_name}_chara_card.png")
    conversion_error = None

    if image_path.lower().endswith('.png'):
        if runtime.embed_json_in_png(chara_card_json, image_path, png_output_path):
            print(f"Created PNG character card: {png_output_path}")
        else:
            png_output_path = None
            conversion_error = "Failed to embed JSON in PNG"
        return png_output_path, conversion_error

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

    return png_output_path, conversion_error


def _cleanup_downloaded_image(runtime, request_data, image_path):
    if image_path and runtime.storage_gateway.exists(image_path) and not request_data.resume_checkpoint_id:
        try:
            runtime.storage_gateway.remove_file(image_path)
            print(f"Cleaned up VNDB image: {image_path}")
            return None
        except Exception as e:
            print(f"Failed to clean up VNDB image: {e}")
    return image_path


def _finalize_character_card_success(runtime, request_data, checkpoint_id, paths, result):
    runtime.checkpoint_gateway.mark_completed(checkpoint_id, final_output_path=paths['json_output_path'])
    image_path = paths['image_path']

    try:
        chara_card_json = runtime.storage_gateway.read_json(paths['json_output_path'])
    except Exception as e:
        return ok_result(
            message=f"角色卡生成完成 (JSON): {paths['json_output_path']}",
            output_path=paths['json_output_path'],
            fields_written=result.get('fields_written', []),
            image_path=image_path,
            warning=f"无法读取JSON用于PNG嵌入: {str(e)}",
            checkpoint_id=checkpoint_id,
        )

    png_output_path = None
    conversion_error = None
    if image_path and runtime.storage_gateway.exists(image_path):
        png_output_path, conversion_error = _embed_json_to_png(
            runtime=runtime,
            request_data=request_data,
            checkpoint_id=checkpoint_id,
            output_dir=paths['output_dir'],
            image_path=image_path,
            chara_card_json=chara_card_json,
        )

        image_path = _cleanup_downloaded_image(runtime, request_data, image_path)

    response_data = ok_result(
        message=f"角色卡生成完成: {paths['json_output_path']}",
        output_path=paths['json_output_path'],
        fields_written=result.get('fields_written', []),
        result=result.get('result', ''),
        checkpoint_id=checkpoint_id,
    )

    if image_path:
        response_data['image_path'] = image_path
    if png_output_path:
        response_data['png_path'] = png_output_path
    if conversion_error:
        response_data['conversion_error'] = conversion_error

    return response_data


def _handle_character_card_failure(runtime, checkpoint_id, result):
    if result.get('can_resume'):
        runtime.checkpoint_gateway.mark_failed(checkpoint_id, result.get('message', '生成失败'))
        return fail_result(
            result.get('message', '生成失败'),
            checkpoint_id=checkpoint_id,
            can_resume=True
        )
    return fail_result(result.get('message', '生成失败'))


def run_generate_character_card_task(
    data,
    runtime
):
    prepared, error = _prepare_generate_character_card_request(data, runtime)
    if error:
        return error

    request_data = prepared['request_data']
    config = prepared['config']
    checkpoint_id = prepared['checkpoint_id']

    all_character_analyses, all_lorebook_entries, script_dir, error = _load_character_analyses(runtime, request_data.role_name)
    if error:
        return error

    all_character_analyses = _compress_character_analyses(
        all_character_analyses=all_character_analyses,
        request_data=request_data,
        config=config,
        checkpoint_id=checkpoint_id,
        runtime=runtime,
    )

    paths = _prepare_output_paths(
        runtime=runtime,
        script_dir=script_dir,
        request_data=request_data,
        checkpoint_id=checkpoint_id,
    )

    llm_interaction = runtime.llm_gateway.create_client(config)
    result = llm_interaction.generate_character_card_with_tools(
        request_data.role_name,
        all_character_analyses,
        all_lorebook_entries,
        paths['json_output_path'],
        request_data.creator,
        request_data.vndb_data,
        request_data.output_language,
        checkpoint_id=checkpoint_id,
        ckpt_messages=prepared['messages'] if request_data.resume_checkpoint_id else None,
        ckpt_fields_data=prepared['fields_data'] if request_data.resume_checkpoint_id else None,
        ckpt_iteration_count=prepared['iteration_count'] if request_data.resume_checkpoint_id else None
    )

    if result.get('success'):
        return _finalize_character_card_success(
            runtime=runtime,
            request_data=request_data,
            checkpoint_id=checkpoint_id,
            paths=paths,
            result=result,
        )

    return _handle_character_card_failure(runtime, checkpoint_id, result)
