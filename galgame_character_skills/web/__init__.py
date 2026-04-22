"""Web 资源模块，提供前端模板与静态资源路径解析入口。"""

from ..utils.path_utils import get_resource_path


def get_template_dir():
    return get_resource_path('web')


__all__ = ["get_template_dir"]
