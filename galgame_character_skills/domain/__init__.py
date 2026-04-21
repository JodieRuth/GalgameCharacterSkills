"""领域层导出模块，集中暴露请求模型与统一服务结果结构。"""

from .task_requests import (
    SummarizeRequest,
    GenerateSkillsRequest,
    GenerateCharacterCardRequest,
)
from .service_result import ServiceResult, ok_result, fail_result

__all__ = [
    "SummarizeRequest",
    "GenerateSkillsRequest",
    "GenerateCharacterCardRequest",
    "ServiceResult",
    "ok_result",
    "fail_result",
]
