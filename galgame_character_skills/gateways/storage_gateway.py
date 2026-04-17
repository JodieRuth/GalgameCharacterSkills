import json
import os
import shutil


class StorageGateway:
    def exists(self, path):
        raise NotImplementedError

    def makedirs(self, path, exist_ok=True):
        raise NotImplementedError

    def read_text(self, path, encoding="utf-8"):
        raise NotImplementedError

    def write_text(self, path, content, encoding="utf-8"):
        raise NotImplementedError

    def read_json(self, path, encoding="utf-8"):
        raise NotImplementedError

    def write_json(self, path, data, encoding="utf-8", ensure_ascii=False, indent=2):
        raise NotImplementedError

    def remove_file(self, path):
        raise NotImplementedError

    def remove_tree(self, path):
        raise NotImplementedError

    def listdir(self, path):
        raise NotImplementedError


class DefaultStorageGateway(StorageGateway):
    def exists(self, path):
        return os.path.exists(path)

    def makedirs(self, path, exist_ok=True):
        os.makedirs(path, exist_ok=exist_ok)

    def read_text(self, path, encoding="utf-8"):
        with open(path, "r", encoding=encoding) as f:
            return f.read()

    def write_text(self, path, content, encoding="utf-8"):
        with open(path, "w", encoding=encoding) as f:
            f.write(content)

    def read_json(self, path, encoding="utf-8"):
        with open(path, "r", encoding=encoding) as f:
            return json.load(f)

    def write_json(self, path, data, encoding="utf-8", ensure_ascii=False, indent=2):
        with open(path, "w", encoding=encoding) as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)

    def remove_file(self, path):
        os.remove(path)

    def remove_tree(self, path):
        shutil.rmtree(path, ignore_errors=True)

    def listdir(self, path):
        return os.listdir(path)


__all__ = ["StorageGateway", "DefaultStorageGateway"]
