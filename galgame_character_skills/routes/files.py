"""文件相关路由注册模块。"""

from flask import request

from ..api.file_api_service import (
    calculate_tokens_result,
    scan_files_result,
    slice_file_result,
    upload_files_result,
)
from ..utils.input_normalization import extract_file_paths


def register_file_routes(app, deps, adapter) -> None:
    """注册文件相关路由。"""

    @app.route("/api/files", methods=["GET"])
    def scan_files():
        """处理资源文件扫描请求。

        Args:
            None

        Returns:
            Response: 文件列表 JSON 响应。

        Raises:
            Exception: 下游文件扫描失败时向上抛出。
        """
        return adapter.run(scan_files_result, deps.file_processor)

    @app.route("/api/files/upload", methods=["POST"])
    def upload_files():
        """处理文件上传请求。

        Args:
            None

        Returns:
            Response: 上传结果 JSON 响应。

        Raises:
            Exception: 文件读取或保存失败时向上抛出。
        """
        files = request.files.getlist("files")
        return adapter.response(upload_files_result(deps.file_processor, files))

    @app.route("/api/files/tokens", methods=["POST"])
    def calculate_tokens():
        """处理文件 token 估算请求。

        Args:
            None

        Returns:
            Response: token 与切片统计 JSON 响应。

        Raises:
            Exception: 请求解析或 token 计算失败时向上抛出。
        """
        return adapter.run_with_body(lambda data: calculate_tokens_result(deps.file_processor, data))

    @app.route("/api/slice", methods=["POST"])
    def slice_file():
        """处理文件切片预估请求。

        Args:
            None

        Returns:
            Response: 切片统计 JSON 响应。

        Raises:
            Exception: 请求解析或切片执行失败时向上抛出。
        """
        return adapter.run_with_body(lambda data: slice_file_result(deps.file_processor, data, extract_file_paths))


__all__ = ["register_file_routes"]
