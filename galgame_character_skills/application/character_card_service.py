import json
import os
from dataclasses import dataclass, field

from ..checkpoint import load_resumable_checkpoint
from .compression_policy import resolve_compression_policy
from .compression_executor import run_compression_pipeline
from .task_prepared import PreparedGenerateCharacterCardTask
from .task_state import CharacterCardResumeState, build_initial_state_factory, build_resume_state_loader
from .task_result_factory import ok_task_result, fail_task_result
from .task_prepare_context import (
    build_on_resumed_logger,
    build_clean_payload_loader,
    build_prepared_state_builder,
    prepare_task_context,
)
from ..files import find_role_analysis_summary_file
from ..utils.request_config import build_llm_config
from ..utils.compression_service import compress_analyses_with_llm
from ..domain import GenerateCharacterCardRequest, fail_result
from ..workspace import get_workspace_cards_dir, get_workspace_summaries_dir


@dataclass(frozen=True)
class CharacterCardTaskResult:
    success: bool
    message: str = ""
    can_resume: bool = False
    fields_written: list = field(default_factory=list)
    result: str = ""


def _to_character_card_task_result(raw_result):
    raw_result = raw_result or {}
    return CharacterCardTaskResult(
        success=bool(raw_result.get("success")),
        message=raw_result.get("message", ""),
        can_resume=bool(raw_result.get("can_resume")),
        fields_written=raw_result.get("fields_written", []),
        result=raw_result.get("result", ""),
    )


_load_resume_character_card_state = build_resume_state_loader(
    CharacterCardResumeState,
    {
        "fields_data": "fields_data",
        "messages": "messages",
        "iteration_count": "iteration_count",
    },
)
_build_initial_character_card_state = build_initial_state_factory(CharacterCardResumeState)
_from_character_card_payload = build_clean_payload_loader(GenerateCharacterCardRequest)
_build_prepared_character_card_task = build_prepared_state_builder(
    PreparedGenerateCharacterCardTask,
    ("fields_data", "messages", "iteration_count"),
)
_on_character_card_resumed = build_on_resumed_logger(
    lambda _request_data, checkpoint_data, _runtime: (
        f"Resuming generate_chara_card: iteration {checkpoint_data.state.iteration_count}, "
        f"fields: {list(checkpoint_data.state.fields_data.keys())}"
    )
)


def _prepare_generate_character_card_request(data, runtime):
    return prepare_task_context(
        data=data,
        runtime=runtime,
        from_payload=_from_character_card_payload,
        config_builder=build_llm_config,
        checkpoint_task_type="generate_chara_card",
        load_resume_state=_load_resume_character_card_state,
        build_initial_state=_build_initial_character_card_state,
        load_resumable_checkpoint_fn=load_resumable_checkpoint,
        build_prepared=_build_prepared_character_card_task,
        on_resumed=_on_character_card_resumed,
    )


def _load_character_analyses(runtime, role_name):
    summaries_root_dir = get_workspace_summaries_dir()
    analysis_file = find_role_analysis_summary_file(summaries_root_dir, role_name)

    if not analysis_file:
        return None, None, fail_result(f'未找到角色 "{role_name}" 的分析文件，请先完成归纳')

    try:
        analysis_data = runtime.storage_gateway.read_json(analysis_file)
    except Exception as e:
        return None, None, fail_result(f'读取分析文件失败: {str(e)}')

    all_character_analyses = analysis_data.get('character_analyses', [])
    all_lorebook_entries = analysis_data.get('lorebook_entries', [])

    if not all_character_analyses:
        return None, None, fail_result('分析数据为空')

    return all_character_analyses, all_lorebook_entries, None


def _compress_character_analyses(all_character_analyses, request_data, config, checkpoint_id, runtime):
    analyses_text = json.dumps(all_character_analyses, ensure_ascii=False)
    raw_estimated_tokens = runtime.estimate_tokens(analyses_text)
    policy = resolve_compression_policy(
        model_name=request_data.model_name,
        raw_estimated_tokens=raw_estimated_tokens,
        force_no_compression=request_data.force_no_compression,
    )
    def _llm_compress(target_budget_tokens):
        print("Using LLM compression for analyses")
        llm_interaction = runtime.llm_gateway.create_client(config)
        return compress_analyses_with_llm(
            analyses=all_character_analyses,
            llm_client=llm_interaction,
            target_budget_tokens=target_budget_tokens,
            checkpoint_id=checkpoint_id,
            ckpt_manager=runtime.checkpoint_gateway,
            estimate_tokens=runtime.estimate_tokens,
        )

    def _fallback_compress(target_budget_tokens):
        print("Using original compression")
        target_count = max(1, len(all_character_analyses) * target_budget_tokens // raw_estimated_tokens)
        return all_character_analyses[:target_count]

    compressed, used_compression, _, _ = run_compression_pipeline(
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
        all_character_analyses = compressed
        compressed_text = json.dumps(all_character_analyses, ensure_ascii=False)
        compressed_tokens = runtime.estimate_tokens(compressed_text)
        print(f"Compressed: {raw_estimated_tokens} -> {compressed_tokens} tokens ({compressed_tokens/raw_estimated_tokens*100:.1f}%)")

    return all_character_analyses


def _prepare_output_paths(runtime, request_data, checkpoint_id):
    cards_root = get_workspace_cards_dir()
    runtime.storage_gateway.makedirs(cards_root, exist_ok=True)
    output_dir = os.path.join(cards_root, f"{request_data.role_name}-character-card")
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
        return ok_task_result(
            message=f"角色卡生成完成 (JSON): {paths['json_output_path']}",
            output_path=paths['json_output_path'],
            fields_written=result.fields_written,
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

    response_data = ok_task_result(
        message=f"角色卡生成完成: {paths['json_output_path']}",
        output_path=paths['json_output_path'],
        fields_written=result.fields_written,
        result=result.result,
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
    if result.can_resume:
        runtime.checkpoint_gateway.mark_failed(checkpoint_id, result.message or '生成失败')
        return fail_task_result(result.message or '生成失败', checkpoint_id=checkpoint_id, can_resume=True)
    return fail_task_result(result.message or '生成失败')


def run_generate_character_card_task(
    data,
    runtime
):
    prepared, error = _prepare_generate_character_card_request(data, runtime)
    if error:
        return error

    request_data = prepared.request_data
    config = prepared.config
    checkpoint_id = prepared.checkpoint_id

    all_character_analyses, all_lorebook_entries, error = _load_character_analyses(runtime, request_data.role_name)
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
        request_data=request_data,
        checkpoint_id=checkpoint_id,
    )

    llm_interaction = runtime.llm_gateway.create_client(config)
    raw_result = llm_interaction.generate_character_card_with_tools(
        request_data.role_name,
        all_character_analyses,
        all_lorebook_entries,
        paths['json_output_path'],
        request_data.creator,
        request_data.vndb_data,
        request_data.output_language,
        checkpoint_id=checkpoint_id,
        ckpt_messages=prepared.messages if request_data.resume_checkpoint_id else None,
        ckpt_fields_data=prepared.fields_data if request_data.resume_checkpoint_id else None,
        ckpt_iteration_count=prepared.iteration_count if request_data.resume_checkpoint_id else None
    )
    result = _to_character_card_task_result(raw_result)

    if result.success:
        return _finalize_character_card_success(
            runtime=runtime,
            request_data=request_data,
            checkpoint_id=checkpoint_id,
            paths=paths,
            result=result,
        )

    return _handle_character_card_failure(runtime, checkpoint_id, result)
