import json
import os

from services.checkpoint_utils import load_resumable_checkpoint
from services.summary_discovery import find_role_analysis_summary_file


def run_generate_character_card_task(
    data,
    ckpt_manager,
    clean_vndb_data,
    get_base_dir,
    estimate_tokens,
    get_model_context_limit,
    calculate_compression_threshold,
    compress_analyses_with_llm,
    build_llm_client,
    download_vndb_image,
    embed_json_in_png
):
    role_name = data.get('role_name', '')
    creator = data.get('creator', '')
    vndb_data_raw = data.get('vndb_data')
    vndb_data = clean_vndb_data(vndb_data_raw)
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
        creator = ckpt['input_params'].get('creator', creator)
        vndb_data = ckpt['input_params'].get('vndb_data', vndb_data)
        vndb_data_raw = ckpt['input_params'].get('vndb_data_raw', vndb_data_raw)
        output_language = ckpt['input_params'].get('output_language', output_language)
        compression_mode = ckpt['input_params'].get('compression_mode', compression_mode)
        force_no_compression = ckpt['input_params'].get('force_no_compression', force_no_compression)
        checkpoint_id = resume_checkpoint_id

        llm_state = ckpt_manager.load_llm_state(checkpoint_id)
        fields_data = llm_state.get('fields_data', {})
        messages = llm_state.get('messages', [])
        iteration_count = llm_state.get('iteration_count', 0)

        print(f"Resuming generate_chara_card: iteration {iteration_count}, fields: {list(fields_data.keys())}")
    else:
        checkpoint_id = ckpt_manager.create_checkpoint(
            task_type='generate_chara_card',
            input_params={
                'role_name': role_name,
                'creator': creator,
                'vndb_data': vndb_data,
                'vndb_data_raw': vndb_data_raw,
                'output_language': output_language,
                'compression_mode': compression_mode,
                'force_no_compression': force_no_compression
            }
        )
        fields_data = {}
        messages = []
        iteration_count = 0

    script_dir = get_base_dir()
    analysis_file = find_role_analysis_summary_file(script_dir, role_name)

    if not analysis_file:
        return {'success': False, 'message': f'未找到角色 "{role_name}" 的分析文件，请先完成归纳'}

    try:
        with open(analysis_file, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
    except Exception as e:
        return {'success': False, 'message': f'读取分析文件失败: {str(e)}'}

    all_character_analyses = analysis_data.get('character_analyses', [])
    all_lorebook_entries = analysis_data.get('lorebook_entries', [])

    if not all_character_analyses:
        return {'success': False, 'message': '分析数据为空'}

    analyses_text = json.dumps(all_character_analyses, ensure_ascii=False)
    raw_estimated_tokens = estimate_tokens(analyses_text)
    model_name = data.get('modelname', '')
    context_limit = get_model_context_limit(model_name)
    context_limit_tokens = calculate_compression_threshold(context_limit)
    target_budget_tokens = context_limit_tokens

    print(f"Model: {model_name}, Context limit: {context_limit}, Threshold: {context_limit_tokens}")
    print(f"Compression mode: {compression_mode}, Force no compression: {force_no_compression}, Raw tokens: {raw_estimated_tokens}, Limit: {context_limit_tokens}")

    if not force_no_compression and raw_estimated_tokens > context_limit_tokens:
        if compression_mode == 'llm':
            print("Using LLM compression for analyses")
            llm_interaction = build_llm_client(config)
            compressed_analyses = compress_analyses_with_llm(all_character_analyses, llm_interaction, target_budget_tokens, checkpoint_id=checkpoint_id)
            all_character_analyses = compressed_analyses
            context_mode = "llm_compressed"
        else:
            print("Using original compression")
            target_count = max(1, len(all_character_analyses) * target_budget_tokens // raw_estimated_tokens)
            all_character_analyses = all_character_analyses[:target_count]
            context_mode = "compressed"

        compressed_text = json.dumps(all_character_analyses, ensure_ascii=False)
        compressed_tokens = estimate_tokens(compressed_text)
        print(f"Compressed: {raw_estimated_tokens} -> {compressed_tokens} tokens ({compressed_tokens/raw_estimated_tokens*100:.1f}%)")
    else:
        if force_no_compression and raw_estimated_tokens > context_limit_tokens:
            context_mode = "full_forced"
            print("Force no compression enabled, using full context despite exceeding limit")
        else:
            context_mode = "full"
        print(f"No compression needed ({raw_estimated_tokens} <= {context_limit_tokens})")

    output_dir = os.path.join(script_dir, f"{role_name}-character-card")
    os.makedirs(output_dir, exist_ok=True)
    json_output_path = os.path.join(output_dir, f"{role_name}_chara_card.json")

    image_path = None
    if vndb_data_raw and vndb_data_raw.get('image_url'):
        image_ext = os.path.splitext(vndb_data_raw['image_url'])[1] or '.jpg'
        ckpt_temp_dir = ckpt_manager.get_temp_dir(checkpoint_id)
        image_path = os.path.join(ckpt_temp_dir, f"{role_name}_vndb{image_ext}")
        if os.path.exists(image_path):
            print(f"VNDB image already exists: {image_path}")
        elif download_vndb_image(vndb_data_raw['image_url'], image_path):
            print(f"Downloaded VNDB image to: {image_path}")
        else:
            image_path = None

    llm_interaction = build_llm_client(config)
    result = llm_interaction.generate_character_card_with_tools(
        role_name,
        all_character_analyses,
        all_lorebook_entries,
        json_output_path,
        creator,
        vndb_data,
        output_language,
        checkpoint_id=checkpoint_id,
        ckpt_messages=messages if resume_checkpoint_id else None,
        ckpt_fields_data=fields_data if resume_checkpoint_id else None,
        ckpt_iteration_count=iteration_count if resume_checkpoint_id else None
    )

    if result.get('success'):
        ckpt_manager.mark_completed(checkpoint_id, final_output_path=json_output_path)
        try:
            with open(json_output_path, 'r', encoding='utf-8') as f:
                chara_card_json = json.load(f)
        except Exception as e:
            return {
                'success': True,
                'message': f'角色卡生成完成 (JSON): {json_output_path}',
                'output_path': json_output_path,
                'fields_written': result.get('fields_written', []),
                'image_path': image_path,
                'warning': f'无法读取JSON用于PNG嵌入: {str(e)}',
                'checkpoint_id': checkpoint_id
            }

        png_output_path = None
        conversion_error = None
        if image_path and os.path.exists(image_path):
            png_output_path = os.path.join(output_dir, f"{role_name}_chara_card.png")

            if image_path.lower().endswith('.png'):
                if embed_json_in_png(chara_card_json, image_path, png_output_path):
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
                    temp_png = os.path.join(ckpt_manager.get_temp_dir(checkpoint_id), f"{role_name}_temp.png")
                    img.save(temp_png, 'PNG', optimize=True)
                    print(f"Converted image to PNG: {temp_png}")
                    if embed_json_in_png(chara_card_json, temp_png, png_output_path):
                        print(f"Created PNG character card with embedded JSON: {png_output_path}")
                    else:
                        png_output_path = None
                        conversion_error = "Failed to embed JSON in converted PNG"
                    if os.path.exists(temp_png):
                        os.remove(temp_png)
                except ImportError:
                    conversion_error = "PIL (Pillow) not installed. Run: pip install Pillow"
                    print(conversion_error)
                    png_output_path = None
                except Exception as e:
                    conversion_error = f"Image conversion failed: {str(e)}"
                    print(conversion_error)
                    png_output_path = None

            if image_path and os.path.exists(image_path) and not checkpoint_id:
                try:
                    os.remove(image_path)
                    print(f"Cleaned up VNDB image: {image_path}")
                    image_path = None
                except Exception as e:
                    print(f"Failed to clean up VNDB image: {e}")

        response_data = {
            'success': True,
            'message': f'角色卡生成完成: {json_output_path}',
            'output_path': json_output_path,
            'fields_written': result.get('fields_written', []),
            'result': result.get('result', ''),
            'checkpoint_id': checkpoint_id
        }

        if image_path:
            response_data['image_path'] = image_path
        if png_output_path:
            response_data['png_path'] = png_output_path
        if conversion_error:
            response_data['conversion_error'] = conversion_error

        return response_data

    if result.get('can_resume'):
        ckpt_manager.mark_failed(checkpoint_id, result.get('message', '生成失败'))
        return {
            'success': False,
            'message': result.get('message', '生成失败'),
            'checkpoint_id': checkpoint_id,
            'can_resume': True
        }
    return {
        'success': False,
        'message': result.get('message', '生成失败')
    }
