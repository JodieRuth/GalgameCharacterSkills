"""配置查询接口模块，对外返回已脱敏的运行配置视图。"""

from typing import Any, Callable

from ..domain import ok_result


def _mask_secret(secret: str) -> str:
    """脱敏敏感字符串。

    Args:
        secret: 原始敏感字符串。

    Returns:
        str: 脱敏后的字符串。

    Raises:
        Exception: 字符串处理失败时向上抛出。
    """
    if not secret:
        return ""
    if len(secret) <= 6:
        return "*" * len(secret)
    return f"{secret[:3]}***{secret[-2:]}"


def get_config_result(get_app_settings: Callable[[], Any]) -> dict[str, Any]:
    """获取应用配置结果。

    Args:
        get_app_settings: 配置加载函数。

    Returns:
        dict[str, Any]: 已脱敏的配置结果。

    Raises:
        Exception: 配置读取失败时向上抛出。
    """
    settings = get_app_settings()
    return ok_result(
        baseurl=settings.baseurl,
        modelname=settings.modelname,
        max_retries=settings.max_retries,
        workspace_dir=settings.workspace_dir,
        has_apikey=bool(settings.apikey),
        apikey_masked=_mask_secret(settings.apikey),
    )


__all__ = ["get_config_result"]
