from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ServiceResult:
    success: bool
    message: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        result = {"success": self.success}
        if self.message is not None:
            result["message"] = self.message
        result.update(self.payload)
        return result


def ok_result(message: str | None = None, **payload):
    return ServiceResult(success=True, message=message, payload=payload).to_dict()


def fail_result(message: str, **payload):
    return ServiceResult(success=False, message=message, payload=payload).to_dict()
