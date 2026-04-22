"""执行器网关模块，提供线程池执行器的抽象与默认实现。"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any


class ExecutorGateway:
    def create(self, max_workers: int) -> Any:
        """创建执行器实例。

        Args:
            max_workers: 最大工作线程数。

        Returns:
            Any: 执行器实例。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError


class DefaultExecutorGateway(ExecutorGateway):
    def create(self, max_workers: int) -> ThreadPoolExecutor:
        """创建线程池执行器。

        Args:
            max_workers: 最大工作线程数。

        Returns:
            ThreadPoolExecutor: 线程池执行器。

        Raises:
            Exception: 执行器创建失败时向上抛出。
        """
        return ThreadPoolExecutor(max_workers=max_workers)


__all__ = ["ExecutorGateway", "DefaultExecutorGateway"]
