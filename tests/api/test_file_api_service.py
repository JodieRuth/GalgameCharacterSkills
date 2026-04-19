from galgame_character_skills.api.file_api_service import (
    scan_files_result,
    calculate_tokens_result,
    slice_file_result,
)
from galgame_character_skills.app import create_app


class DummyFileProcessor:
    def __init__(self):
        self.raise_error = False

    def scan_resource_files(self):
        return ["a.md", "b.txt"]

    def calculate_tokens(self, file_path):
        if self.raise_error:
            raise RuntimeError("boom")
        return 12345

    def calculate_slices(self, token_count, slice_size_k=50):
        return 3

    def slice_multiple_files(self, file_paths, slice_size_k=50):
        if self.raise_error:
            raise RuntimeError("slice boom")
        return ["s1", "s2"]


def test_scan_files_result_success():
    result = scan_files_result(DummyFileProcessor())
    assert result["success"] is True
    assert result["files"] == ["a.md", "b.txt"]


def test_calculate_tokens_result_requires_file_path():
    fp = DummyFileProcessor()
    no_path = calculate_tokens_result(fp, {})
    assert no_path["success"] is False


def test_calculate_tokens_result_handles_processor_error():
    fp = DummyFileProcessor()
    fp.raise_error = True
    failed = calculate_tokens_result(fp, {"file_path": "x.md"})
    assert failed["success"] is False
    assert "boom" in failed["message"]


def test_calculate_tokens_result_success():
    result = calculate_tokens_result(DummyFileProcessor(), {"file_path": "x.md", "slice_size_k": 40})
    assert result["success"] is True
    assert result["token_count"] == 12345
    assert result["slice_count"] == 3


def test_slice_file_result_requires_files():
    fp = DummyFileProcessor()
    extract = lambda data: []
    result = slice_file_result(fp, {}, extract)
    assert result["success"] is False


def test_slice_file_result_success():
    fp = DummyFileProcessor()
    extract_ok = lambda data: ["a.md", "b.md"]
    ok = slice_file_result(fp, {"slice_size_k": 50}, extract_ok)
    assert ok["success"] is True
    assert ok["slice_count"] == 2
    assert ok["file_count"] == 2


def test_file_routers_tokens_endpoint():
    class DummyDeps:
        file_processor = DummyFileProcessor()
        r18_traits = set()

    class DummyRuntime:
        checkpoint_gateway = object()
        vndb_gateway = object()

    app = create_app(app_dependencies=DummyDeps(), task_runtime=DummyRuntime())
    with app.test_client() as client:
        token_resp = client.post("/api/files/tokens", json={"file_path": "x.md", "slice_size_k": 50})
        assert token_resp.status_code == 200
        token_data = token_resp.get_json()
        assert token_data["success"] is True
        assert "token_count" in token_data
        assert "slice_count" in token_data


def test_file_routers_slice_endpoint():
    class DummyDeps:
        file_processor = DummyFileProcessor()
        r18_traits = set()

    class DummyRuntime:
        checkpoint_gateway = object()
        vndb_gateway = object()

    app = create_app(app_dependencies=DummyDeps(), task_runtime=DummyRuntime())
    with app.test_client() as client:
        slice_resp = client.post("/api/slice", json={"file_paths": ["a.md", "b.md"], "slice_size_k": 50})
        assert slice_resp.status_code == 200
        slice_data = slice_resp.get_json()
        assert slice_data["success"] is True
        assert "slice_count" in slice_data
        assert "file_count" in slice_data
