from ..utils.path_utils import get_resource_path


def get_template_dir():
    return get_resource_path('web')


__all__ = ["get_template_dir"]
