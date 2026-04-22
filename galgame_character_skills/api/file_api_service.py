"""文件接口模块，负责文件扫描、上传、切片与 token 估算的薄编排。"""

from typing import Any, Callable

from ..domain import ok_result, fail_result
from .validators import require_non_empty_field, require_condition


def scan_files_result(file_processor: Any) -> dict[str, Any]:
    """扫描资源文件列表。

    Args:
        file_processor: 文件处理器。

    Returns:
        dict[str, Any]: 文件列表结果。

    Raises:
        Exception: 文件扫描失败时向上抛出。
    """
    files = file_processor.scan_resource_files()
    return ok_result(files=files)


def upload_files_result(file_processor: Any, files: list[Any]) -> dict[str, Any]:
    """上传文件到工作区。

    Args:
        file_processor: 文件处理器。
        files: 上传文件列表。

    Returns:
        dict[str, Any]: 上传结果。

    Raises:
        Exception: 文件保存异常未被内部拦截时向上抛出。
    """
    if not files:
        return fail_result('请先选择要上传的文件')
    try:
        saved_files = file_processor.save_uploaded_files(files)
        if not saved_files:
            return fail_result('未检测到可上传的 .txt/.md 文件')
        return ok_result(
            message=f'上传完成，共保存 {len(saved_files)} 个文件',
            files=saved_files,
        )
    except Exception as e:
        return fail_result(f'上传失败: {str(e)}')


@require_non_empty_field("file_path", "未提供文件路径", data_arg_index=1)
def calculate_tokens_result(
    file_processor: Any,
    data: dict[str, Any],
) -> dict[str, Any]:
    """计算文件 token 和切片数量。

    Args:
        file_processor: 文件处理器。
        data: 请求数据。

    Returns:
        dict[str, Any]: token 统计结果。

    Raises:
        Exception: 文件读取异常未被内部拦截时向上抛出。
    """
    file_path = data.get('file_path', '')
    slice_size_k = data.get('slice_size_k', 50)
    try:
        token_count = file_processor.calculate_tokens(file_path)
        slice_count = file_processor.calculate_slices(token_count, slice_size_k)
        return ok_result(
            token_count=token_count,
            slice_count=slice_count,
            formatted_tokens=f"{token_count:,}"
        )
    except Exception as e:
        return fail_result(str(e))


@require_condition(
    lambda data, _file_processor, extract_file_paths: bool(extract_file_paths(data)),
    "请先选择文件",
    data_arg_index=1,
)
def slice_file_result(
    file_processor: Any,
    data: dict[str, Any],
    extract_file_paths: Callable[[dict[str, Any]], list[str]],
) -> dict[str, Any]:
    """执行文件切片预估。

    Args:
        file_processor: 文件处理器。
        data: 请求数据。
        extract_file_paths: 文件路径提取函数。

    Returns:
        dict[str, Any]: 切片统计结果。

    Raises:
        Exception: 切片异常未被内部拦截时向上抛出。
    """
    slice_size_k = data.get('slice_size_k', 50)
    file_paths = extract_file_paths(data)

    try:
        slices = file_processor.slice_multiple_files(file_paths, slice_size_k)
        file_count = len(file_paths)
        return ok_result(
            message=f'已合并 {file_count} 个文件并切片，共 {len(slices)} 个切片',
            slice_count=len(slices),
            file_count=file_count
        )
    except Exception as e:
        return fail_result(f'切片失败: {str(e)}')
