"""统一服务结果模块，定义 success/message/payload 形式的返回结构。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ServiceResult:
    success: bool
    message: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典结果。

        Args:
            None

        Returns:
            dict[str, Any]: 标准结果字典。

        Raises:
            Exception: 结果转换失败时向上抛出。
        """
        result = {"success": self.success}
        if self.message is not None:
            result["message"] = self.message
        result.update(self.payload)
        return result


def ok_result(message: str | None = None, **payload: Any) -> dict[str, Any]:
    """构造成功结果。

    Args:
        message: 结果消息。
        **payload: 额外返回字段。

    Returns:
        dict[str, Any]: 成功结果字典。

    Raises:
        Exception: 结果构造失败时向上抛出。
    """
    return ServiceResult(success=True, message=message, payload=payload).to_dict()


def fail_result(message: str, **payload: Any) -> dict[str, Any]:
    """构造失败结果。

    Args:
        message: 错误消息。
        **payload: 额外返回字段。

    Returns:
        dict[str, Any]: 失败结果字典。

    Raises:
        Exception: 结果构造失败时向上抛出。
    """
    return ServiceResult(success=False, message=message, payload=payload).to_dict()
