"""文件处理模块，负责上传、扫描、token 计算与文本切片操作。"""

import os
import tiktoken
from typing import Any
from werkzeug.utils import secure_filename

from ..utils.path_utils import get_base_dir


class FileProcessor:
    def __init__(self) -> None:
        """初始化文件处理器。

        Args:
            None

        Returns:
            None

        Raises:
            Exception: 目录或分词器初始化失败时向上抛出。
        """
        self.resource_dir = self._get_resource_dir()
        os.makedirs(self.resource_dir, exist_ok=True)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def _get_base_dir(self) -> str:
        """获取项目根目录。

        Args:
            None

        Returns:
            str: 项目根目录。

        Raises:
            Exception: 路径获取失败时向上抛出。
        """
        return get_base_dir()
    
    def _get_resource_dir(self) -> str:
        """获取资源目录。

        Args:
            None

        Returns:
            str: 资源目录路径。

        Raises:
            Exception: 路径拼接失败时向上抛出。
        """
        return os.path.join(self._get_base_dir(), 'resource')

    @staticmethod
    def _is_supported_text_file(filename: str) -> bool:
        """判断是否为支持的文本文件。

        Args:
            filename: 文件名。

        Returns:
            bool: 是否支持。

        Raises:
            Exception: 文件名处理失败时向上抛出。
        """
        lower = filename.lower()
        return lower.endswith(".txt") or lower.endswith(".md")
    
    def scan_resource_files(self) -> list[str]:
        """扫描资源目录中的文本文件。

        Args:
            None

        Returns:
            list[str]: 文件路径列表。

        Raises:
            Exception: 目录扫描失败时向上抛出。
        """
        files = []
        if os.path.exists(self.resource_dir):
            for file in os.listdir(self.resource_dir):
                file_path = os.path.join(self.resource_dir, file)
                if os.path.isfile(file_path) and self._is_supported_text_file(file):
                    files.append(file_path)
        return files

    def save_uploaded_files(self, uploaded_files: list[Any]) -> list[str]:
        """保存上传文件到资源目录。

        Args:
            uploaded_files: 上传文件对象列表。

        Returns:
            list[str]: 已保存文件路径列表。

        Raises:
            Exception: 文件保存失败时向上抛出。
        """
        saved_files = []
        for uploaded in uploaded_files:
            raw_name = getattr(uploaded, "filename", "") or ""
            safe_name = secure_filename(raw_name)
            if not safe_name or not self._is_supported_text_file(safe_name):
                continue

            save_path = os.path.join(self.resource_dir, safe_name)
            uploaded.save(save_path)
            saved_files.append(save_path)
        return saved_files
    
    def calculate_tokens(self, file_path: str) -> int:
        """计算文件 token 数。

        Args:
            file_path: 文件路径。

        Returns:
            int: token 数。

        Raises:
            Exception: 文件读取异常未被内部拦截时向上抛出。
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            tokens = self.tokenizer.encode(content)
            return len(tokens)
        except Exception as e:
            return 0
    
    def calculate_slices(self, token_count: int, slice_size_k: int = 50) -> int:
        """计算切片数量。

        Args:
            token_count: token 数。
            slice_size_k: 每片大小，单位为千 token。

        Returns:
            int: 切片数量。

        Raises:
            Exception: 计算失败时向上抛出。
        """
        slice_size = slice_size_k * 1000
        return (token_count // slice_size) + 1
    
    def slice_multiple_files(self, file_paths: list[str], slice_size_k: int = 50) -> list[str]:
        """合并并切分多个文本文件。

        Args:
            file_paths: 文件路径列表。
            slice_size_k: 每片大小，单位为千 token。

        Returns:
            list[str]: 切片内容列表。

        Raises:
            Exception: 文件读取或切片异常未被内部拦截时向上抛出。
        """
        try:
            all_lines = []
            for file_path in file_paths:
                with open(file_path, 'r', encoding='utf-8') as f:
                    all_lines.extend(f.readlines())
            
            total_content = ''.join(all_lines)
            total_tokens = len(self.tokenizer.encode(total_content))
            slice_size = slice_size_k * 1000
            slice_count = (total_tokens // slice_size) + 1
            
            lines_per_slice = len(all_lines) // slice_count
            slices = []
            for i in range(slice_count):
                start_line = i * lines_per_slice
                end_line = (i + 1) * lines_per_slice if i < slice_count - 1 else len(all_lines)
                slice_content = ''.join(all_lines[start_line:end_line])
                slices.append(slice_content)
            return slices
        except Exception as e:
            return []

