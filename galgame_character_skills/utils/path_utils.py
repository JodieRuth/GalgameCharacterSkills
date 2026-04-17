import os
import sys


def _package_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(_package_root())


def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = _package_root()
    return os.path.join(base_path, relative_path)
