"""请求配置解析模块，将原始请求数据转换为标准化 LLM 配置。"""

from ..config import get_app_settings


def _resolve_optional_string(value, default):
    if value is None:
        return default
    if isinstance(value, str) and value.strip() == "":
        return default
    return value


def _resolve_max_retries(value, default):
    if value in (None, "", 0):
        return default
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def build_llm_config(data):
    settings = get_app_settings()
    data = data or {}
    return {
        'baseurl': _resolve_optional_string(data.get('baseurl'), settings.baseurl),
        'modelname': _resolve_optional_string(data.get('modelname'), settings.modelname),
        'apikey': _resolve_optional_string(data.get('apikey'), settings.apikey),
        'max_retries': _resolve_max_retries(data.get('max_retries'), settings.max_retries),
    }
