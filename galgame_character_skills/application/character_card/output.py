"""角色卡输出处理模块，负责路径准备、图片处理与成功响应组装。"""

import os
from dataclasses import dataclass
from typing import Any

from ..app_container import TaskRuntimeDependencies
from ..shared.runtime_logging import log_message
from ..shared.task_result_factory import ok_task_result
from ...domain import GenerateCharacterCardRequest


@dataclass(frozen=True)
class CharacterCardOutputPaths:
    """角色卡输出路径模型。

    封装角色卡 JSON、图片与输出目录的路径信息。
    """

    output_dir: str
    json_output_path: str
    image_path: str | None = None

    def __getitem__(self, key):
        """提供兼容字典式读取的访问方式。

        Args:
            key: 字段名。

        Returns:
            Any: 对应字段值。

        Raises:
            AttributeError: 字段不存在时抛出。
        """
        return getattr(self, key)


def prepare_output_paths(
    runtime: TaskRuntimeDependencies,
    request_data: GenerateCharacterCardRequest,
    checkpoint_id: str,
) -> CharacterCardOutputPaths:
    """准备角色卡输出路径。

    Args:
        runtime: 任务运行时依赖。
        request_data: 角色卡生成请求。
        checkpoint_id: checkpoint 标识。

    Returns:
        CharacterCardOutputPaths: 输出路径集合。

    Raises:
        Exception: 目录创建或图片下载失败时向上抛出。
    """
    cards_root = runtime.get_workspace_cards_dir()
    runtime.storage_gateway.makedirs(cards_root, exist_ok=True)
    output_dir = os.path.join(cards_root, f"{request_data.role_name}-character-card")
    runtime.storage_gateway.makedirs(output_dir, exist_ok=True)
    json_output_path = os.path.join(output_dir, f"{request_data.role_name}_chara_card.json")

    image_path = None
    if request_data.vndb_data_raw and request_data.vndb_data_raw.get("image_url"):
        image_ext = os.path.splitext(request_data.vndb_data_raw["image_url"])[1] or ".jpg"
        ckpt_temp_dir = runtime.checkpoint_gateway.get_temp_dir(checkpoint_id)
        image_path = os.path.join(ckpt_temp_dir, f"{request_data.role_name}_vndb{image_ext}")
        if runtime.storage_gateway.exists(image_path):
            log_message(f"VNDB image already exists: {image_path}", runtime=runtime)
        elif runtime.download_vndb_image(request_data.vndb_data_raw["image_url"], image_path):
            log_message(f"Downloaded VNDB image to: {image_path}", runtime=runtime)
        else:
            image_path = None

    return CharacterCardOutputPaths(
        output_dir=output_dir,
        json_output_path=json_output_path,
        image_path=image_path,
    )


def build_character_card_success_response(
    paths: CharacterCardOutputPaths,
    checkpoint_id: str,
    result: Any,
    image_path: str | None,
    png_output_path: str | None,
    conversion_error: str | None,
) -> dict[str, Any]:
    """构造角色卡成功响应。

    Args:
        paths: 输出路径集合。
        checkpoint_id: checkpoint 标识。
        result: 角色卡任务结果。
        image_path: 原始图片路径。
        png_output_path: PNG 输出路径。
        conversion_error: PNG 转换错误。

    Returns:
        dict[str, Any]: 成功响应数据。

    Raises:
        Exception: 响应构造失败时向上抛出。
    """
    response_data = ok_task_result(
        message=f"角色卡生成完成: {paths.json_output_path}",
        output_path=paths.json_output_path,
        fields_written=result.fields_written,
        result=result.result,
        checkpoint_id=checkpoint_id,
    )

    if image_path:
        response_data["image_path"] = image_path
    if png_output_path:
        response_data["png_path"] = png_output_path
    if conversion_error:
        response_data["conversion_error"] = conversion_error
    return response_data


def embed_json_to_png(
    runtime: TaskRuntimeDependencies,
    request_data: GenerateCharacterCardRequest,
    checkpoint_id: str,
    output_dir: str,
    image_path: str,
    chara_card_json: dict[str, Any],
) -> tuple[str | None, str | None]:
    """将角色卡 JSON 嵌入 PNG。

    Args:
        runtime: 任务运行时依赖。
        request_data: 角色卡生成请求。
        checkpoint_id: checkpoint 标识。
        output_dir: 输出目录。
        image_path: 原始图片路径。
        chara_card_json: 角色卡 JSON 数据。

    Returns:
        tuple[str | None, str | None]: PNG 输出路径和错误信息。

    Raises:
        Exception: 图片处理异常未被内部拦截时向上抛出。
    """
    png_output_path = os.path.join(output_dir, f"{request_data.role_name}_chara_card.png")
    conversion_error = None

    if image_path.lower().endswith(".png"):
        if runtime.embed_json_in_png(chara_card_json, image_path, png_output_path):
            log_message(f"Created PNG character card: {png_output_path}", runtime=runtime)
        else:
            png_output_path = None
            conversion_error = "Failed to embed JSON in PNG"
        return png_output_path, conversion_error

    try:
        from PIL import Image

        img = Image.open(image_path)
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = background
        else:
            img = img.convert("RGB")

        temp_png = os.path.join(runtime.checkpoint_gateway.get_temp_dir(checkpoint_id), f"{request_data.role_name}_temp.png")
        img.save(temp_png, "PNG", optimize=True)
        log_message(f"Converted image to PNG: {temp_png}", runtime=runtime)

        if runtime.embed_json_in_png(chara_card_json, temp_png, png_output_path):
            log_message(f"Created PNG character card with embedded JSON: {png_output_path}", runtime=runtime)
        else:
            png_output_path = None
            conversion_error = "Failed to embed JSON in converted PNG"

        if runtime.storage_gateway.exists(temp_png):
            runtime.storage_gateway.remove_file(temp_png)
    except ImportError:
        conversion_error = "PIL (Pillow) not installed. Run: pip install Pillow"
        log_message(conversion_error, runtime=runtime)
        png_output_path = None
    except Exception as exc:
        conversion_error = f"Image conversion failed: {str(exc)}"
        log_message(conversion_error, runtime=runtime)
        png_output_path = None

    return png_output_path, conversion_error


def cleanup_downloaded_image(
    runtime: TaskRuntimeDependencies,
    request_data: GenerateCharacterCardRequest,
    image_path: str | None,
) -> str | None:
    """清理临时下载图片。

    Args:
        runtime: 任务运行时依赖。
        request_data: 角色卡生成请求。
        image_path: 图片路径。

    Returns:
        str | None: 保留的图片路径。

    Raises:
        Exception: 文件删除异常未被内部拦截时向上抛出。
    """
    if image_path and runtime.storage_gateway.exists(image_path) and not request_data.resume_checkpoint_id:
        try:
            runtime.storage_gateway.remove_file(image_path)
            log_message(f"Cleaned up VNDB image: {image_path}", runtime=runtime)
            return None
        except Exception as exc:
            log_message(f"Failed to clean up VNDB image: {exc}", runtime=runtime)
    return image_path


def finalize_character_card_success(
    runtime: TaskRuntimeDependencies,
    request_data: GenerateCharacterCardRequest,
    checkpoint_id: str,
    paths: CharacterCardOutputPaths,
    result: Any,
) -> dict[str, Any]:
    """完成角色卡成功流程。

    Args:
        runtime: 任务运行时依赖。
        request_data: 角色卡生成请求。
        checkpoint_id: checkpoint 标识。
        paths: 输出路径集合。
        result: 角色卡任务结果。

    Returns:
        dict[str, Any]: 成功响应数据。

    Raises:
        Exception: JSON 读取、PNG 嵌入或落盘失败时向上抛出。
    """
    runtime.checkpoint_gateway.mark_completed(checkpoint_id, final_output_path=paths.json_output_path)
    image_path = paths.image_path

    try:
        chara_card_json = runtime.storage_gateway.read_json(paths.json_output_path)
    except Exception as exc:
        return ok_task_result(
            message=f"角色卡生成完成 (JSON): {paths.json_output_path}",
            output_path=paths.json_output_path,
            fields_written=result.fields_written,
            image_path=image_path,
            warning=f"无法读取JSON用于PNG嵌入: {str(exc)}",
            checkpoint_id=checkpoint_id,
        )

    png_output_path = None
    conversion_error = None
    if image_path and runtime.storage_gateway.exists(image_path):
        png_output_path, conversion_error = embed_json_to_png(
            runtime=runtime,
            request_data=request_data,
            checkpoint_id=checkpoint_id,
            output_dir=paths.output_dir,
            image_path=image_path,
            chara_card_json=chara_card_json,
        )

        image_path = cleanup_downloaded_image(runtime, request_data, image_path)

    return build_character_card_success_response(
        paths=paths,
        checkpoint_id=checkpoint_id,
        result=result,
        image_path=image_path,
        png_output_path=png_output_path,
        conversion_error=conversion_error,
    )


__all__ = [
    "CharacterCardOutputPaths",
    "prepare_output_paths",
    "build_character_card_success_response",
    "embed_json_to_png",
    "cleanup_downloaded_image",
    "finalize_character_card_success",
]
