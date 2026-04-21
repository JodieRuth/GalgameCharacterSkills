"""执行器网关模块，提供线程池执行器的抽象与默认实现。"""

from concurrent.futures import ThreadPoolExecutor


class ExecutorGateway:
    def create(self, max_workers):
        raise NotImplementedError


class DefaultExecutorGateway(ExecutorGateway):
    def create(self, max_workers):
        return ThreadPoolExecutor(max_workers=max_workers)


__all__ = ["ExecutorGateway", "DefaultExecutorGateway"]
