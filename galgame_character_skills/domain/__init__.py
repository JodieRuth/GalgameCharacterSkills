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
