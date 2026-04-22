"""请求配置解析模块，将原始请求数据转换为标准化 LLM 配置。"""

from typing import Any

from .settings import get_app_settings


def _resolve_optional_string(value: Any, default: str) -> Any:
    """解析可选字符串配置值。

    Args:
        value: 原始值。
        default: 默认值。

    Returns:
        Any: 解析后的值。

    Raises:
        Exception: 值解析失败时向上抛出。
    """
    if value is None:
        return default
    if isinstance(value, str) and value.strip() == "":
        return default
    return value


def _resolve_max_retries(value: Any, default: int | None) -> int | None:
    """解析最大重试次数配置。

    Args:
        value: 原始值。
        default: 默认值。

    Returns:
        int | None: 解析后的最大重试次数。

    Raises:
        Exception: 值解析失败时向上抛出。
    """
    if value in (None, "", 0):
        return default
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def build_llm_config(data: dict[str, Any] | None) -> dict[str, Any]:
    """构造标准化的 LLM 配置。

    Args:
        data: 原始请求数据。

    Returns:
        dict[str, Any]: 标准化后的 LLM 配置。

    Raises:
        Exception: 配置构造失败时向上抛出。
    """
    settings = get_app_settings()
    data = data or {}
    return {
        'baseurl': _resolve_optional_string(data.get('baseurl'), settings.baseurl),
        'modelname': _resolve_optional_string(data.get('modelname'), settings.modelname),
        'apikey': _resolve_optional_string(data.get('apikey'), settings.apikey),
        'max_retries': _resolve_max_retries(data.get('max_retries'), settings.max_retries),
    }
