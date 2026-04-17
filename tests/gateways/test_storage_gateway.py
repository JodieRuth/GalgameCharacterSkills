from unittest.mock import mock_open

from galgame_character_skills.gateways.storage_gateway import DefaultStorageGateway


def test_storage_gateway_delegates_exists_makedirs_and_listdir(monkeypatch):
    called = {}

    monkeypatch.setattr(
        "galgame_character_skills.gateways.storage_gateway.os.path.exists",
        lambda path: path == "a.txt",
    )

    def fake_makedirs(path, exist_ok=True):
        called["makedirs"] = (path, exist_ok)

    def fake_listdir(path):
        called["listdir"] = path
        return ["a.txt", "b.txt"]

    monkeypatch.setattr("galgame_character_skills.gateways.storage_gateway.os.makedirs", fake_makedirs)
    monkeypatch.setattr("galgame_character_skills.gateways.storage_gateway.os.listdir", fake_listdir)

    gateway = DefaultStorageGateway()
    assert gateway.exists("a.txt") is True
    assert gateway.exists("missing.txt") is False
    gateway.makedirs("dir1", exist_ok=False)
    assert called["makedirs"] == ("dir1", False)
    assert gateway.listdir("dir1") == ["a.txt", "b.txt"]
    assert called["listdir"] == "dir1"


def test_storage_gateway_read_and_write_text(monkeypatch):
    gateway = DefaultStorageGateway()

    read_mock = mock_open(read_data="hello")
    monkeypatch.setattr("builtins.open", read_mock)
    assert gateway.read_text("a.txt") == "hello"
    read_mock.assert_called_with("a.txt", "r", encoding="utf-8")

    write_mock = mock_open()
    monkeypatch.setattr("builtins.open", write_mock)
    gateway.write_text("b.txt", "world")
    write_mock.assert_called_with("b.txt", "w", encoding="utf-8")
    write_mock().write.assert_called_once_with("world")


def test_storage_gateway_read_and_write_json(monkeypatch):
    called = {}
    gateway = DefaultStorageGateway()

    open_mock = mock_open()
    monkeypatch.setattr("builtins.open", open_mock)

    def fake_load(handle):
        called["load"] = True
        return {"k": 1}

    def fake_dump(data, handle, ensure_ascii=False, indent=2):
        called["dump"] = (data, ensure_ascii, indent)

    monkeypatch.setattr("galgame_character_skills.gateways.storage_gateway.json.load", fake_load)
    monkeypatch.setattr("galgame_character_skills.gateways.storage_gateway.json.dump", fake_dump)

    assert gateway.read_json("in.json") == {"k": 1}
    gateway.write_json("out.json", {"x": 2}, ensure_ascii=True, indent=4)

    assert called["load"] is True
    assert called["dump"] == ({"x": 2}, True, 4)


def test_storage_gateway_remove_file_and_tree(monkeypatch):
    called = {}

    def fake_remove(path):
        called["remove"] = path

    def fake_rmtree(path, ignore_errors=True):
        called["rmtree"] = (path, ignore_errors)

    monkeypatch.setattr("galgame_character_skills.gateways.storage_gateway.os.remove", fake_remove)
    monkeypatch.setattr("galgame_character_skills.gateways.storage_gateway.shutil.rmtree", fake_rmtree)

    gateway = DefaultStorageGateway()
    gateway.remove_file("a.txt")
    gateway.remove_tree("dir1")

    assert called["remove"] == "a.txt"
    assert called["rmtree"] == ("dir1", True)
