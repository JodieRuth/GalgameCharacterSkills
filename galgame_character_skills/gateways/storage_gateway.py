"""存储网关模块，封装文件读写、目录操作与 JSON 持久化。"""

import json
import os
import shutil
from typing import Any


class StorageGateway:
    def exists(self, path: str) -> bool:
        """检查路径是否存在。

        Args:
            path: 目标路径。

        Returns:
            bool: 路径是否存在。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        """创建目录。

        Args:
            path: 目录路径。
            exist_ok: 目录已存在时是否忽略。

        Returns:
            None

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """读取文本文件。

        Args:
            path: 文件路径。
            encoding: 文件编码。

        Returns:
            str: 文件内容。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> None:
        """写入文本文件。

        Args:
            path: 文件路径。
            content: 文本内容。
            encoding: 文件编码。

        Returns:
            None

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def read_json(self, path: str, encoding: str = "utf-8") -> Any:
        """读取 JSON 文件。

        Args:
            path: 文件路径。
            encoding: 文件编码。

        Returns:
            Any: JSON 数据。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def write_json(
        self,
        path: str,
        data: Any,
        encoding: str = "utf-8",
        ensure_ascii: bool = False,
        indent: int = 2,
    ) -> None:
        """写入 JSON 文件。

        Args:
            path: 文件路径。
            data: JSON 数据。
            encoding: 文件编码。
            ensure_ascii: 是否转义非 ASCII 字符。
            indent: 缩进宽度。

        Returns:
            None

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def remove_file(self, path: str) -> None:
        """删除文件。

        Args:
            path: 文件路径。

        Returns:
            None

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def remove_tree(self, path: str) -> None:
        """删除目录树。

        Args:
            path: 目录路径。

        Returns:
            None

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def listdir(self, path: str) -> list[str]:
        """列出目录内容。

        Args:
            path: 目录路径。

        Returns:
            list[str]: 目录项列表。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError


class DefaultStorageGateway(StorageGateway):
    def exists(self, path: str) -> bool:
        """检查路径是否存在。"""
        return os.path.exists(path)

    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        """创建目录。"""
        os.makedirs(path, exist_ok=exist_ok)

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """读取文本文件。"""
        with open(path, "r", encoding=encoding) as f:
            return f.read()

    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> None:
        """写入文本文件。"""
        with open(path, "w", encoding=encoding) as f:
            f.write(content)

    def read_json(self, path: str, encoding: str = "utf-8") -> Any:
        """读取 JSON 文件。"""
        with open(path, "r", encoding=encoding) as f:
            return json.load(f)

    def write_json(
        self,
        path: str,
        data: Any,
        encoding: str = "utf-8",
        ensure_ascii: bool = False,
        indent: int = 2,
    ) -> None:
        """写入 JSON 文件。"""
        with open(path, "w", encoding=encoding) as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)

    def remove_file(self, path: str) -> None:
        """删除文件。"""
        os.remove(path)

    def remove_tree(self, path: str) -> None:
        """删除目录树。"""
        shutil.rmtree(path, ignore_errors=True)

    def listdir(self, path: str) -> list[str]:
        """列出目录内容。"""
        return os.listdir(path)


__all__ = ["StorageGateway", "DefaultStorageGateway"]
