"""应用配置模块，负责读取环境变量、dotenv 与缓存化配置对象。"""

import os
import sys
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class AppSettings:
    baseurl: str = ""
    modelname: str = ""
    apikey: str = ""
    max_retries: int | None = None
    workspace_dir: str = ""


def _parse_dotenv_file(dotenv_path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    if not os.path.exists(dotenv_path):
        return values

    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key:
                    continue
                if value and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                values[key] = value
    except Exception:
        return {}

    return values


def _read_config_value(dotenv_values: dict[str, str], env_key: str, default: str = "") -> str:
    if env_key in os.environ:
        return os.environ.get(env_key, "").strip()
    if env_key in dotenv_values:
        return dotenv_values[env_key].strip()
    return default


def _parse_positive_int(value: str) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(package_root)


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    base_dir = get_base_dir()
    dotenv_path = os.path.join(base_dir, ".env")
    dotenv_values = _parse_dotenv_file(dotenv_path)

    baseurl = _read_config_value(dotenv_values, "GCS_BASEURL", "")
    modelname = _read_config_value(dotenv_values, "GCS_MODELNAME", "")
    apikey = _read_config_value(dotenv_values, "GCS_APIKEY", "")
    max_retries = _parse_positive_int(_read_config_value(dotenv_values, "GCS_MAX_RETRIES", ""))
    workspace_dir = _read_config_value(dotenv_values, "GCS_WORKSPACE_DIR", "")

    return AppSettings(
        baseurl=baseurl,
        modelname=modelname,
        apikey=apikey,
        max_retries=max_retries,
        workspace_dir=workspace_dir,
    )


def reset_app_settings_cache():
    get_app_settings.cache_clear()


__all__ = ["AppSettings", "get_app_settings", "reset_app_settings_cache"]
