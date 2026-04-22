"""VNDB 数据工具模块，负责特征词加载与角色数据清洗规范化。"""

import base64
import json
import os
from typing import Any


def load_r18_traits(base_dir: str) -> set[str]:
    """加载 R18 特征词集合。

    Args:
        base_dir: 应用根目录。

    Returns:
        set[str]: R18 特征词集合。

    Raises:
        Exception: 文件读取异常未被内部拦截时向上抛出。
    """
    try:
        json_path = os.path.join(base_dir, 'vndb', 'r18_traits.json')
        if not os.path.exists(json_path):
            json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'r18_traits.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        encoded_traits = data.get('encoded_traits', [])
        return {base64.b64decode(t.encode()).decode('utf-8') for t in encoded_traits}
    except Exception as e:
        print(f"Warning: Failed to load r18_traits: {e}")
        return set()


def clean_vndb_data(vndb_data: Any) -> Any:
    """清洗 VNDB 数据中的不必要字段。

    Args:
        vndb_data: 原始 VNDB 数据。

    Returns:
        Any: 清洗后的 VNDB 数据。

    Raises:
        Exception: 数据清洗失败时向上抛出。
    """
    if vndb_data and isinstance(vndb_data, dict):
        cleaned = vndb_data.copy()
        cleaned.pop('image_url', None)
        return cleaned
    return vndb_data
