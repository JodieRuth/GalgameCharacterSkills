from galgame_character_skills.domain.task_requests import (
    SummarizeRequest,
    GenerateSkillsRequest,
    GenerateCharacterCardRequest,
)


def _clean_vndb_data(raw):
    if not raw:
        return None
    return {"cleaned": True, "raw": raw}


def _extract_file_paths(payload):
    return payload.get("file_paths", [])


def test_summarize_request_from_payload_and_checkpoint_roundtrip():
    payload = {
        "role_name": "A",
        "instruction": "I",
        "concurrency": 2,
        "mode": "skills",
        "resume_checkpoint_id": "ckpt1",
        "output_language": "zh",
        "vndb_data": {"id": 1},
        "slice_size_k": 80,
        "file_paths": ["a.md"],
    }
    req = SummarizeRequest.from_payload(payload, _clean_vndb_data, _extract_file_paths)
    assert req.role_name == "A"
    assert req.vndb_data["cleaned"] is True
    assert req.file_paths == ["a.md"]

    req.apply_checkpoint({"role_name": "B", "concurrency": 4, "file_paths": ["b.md"]})
    ckpt_input = req.to_checkpoint_input()
    assert ckpt_input["role_name"] == "B"
    assert ckpt_input["concurrency"] == 4
    assert ckpt_input["file_paths"] == ["b.md"]


def test_generate_skills_request_maps_model_name_field():
    req = GenerateSkillsRequest.from_payload(
        {"role_name": "R", "vndb_data": {"x": 1}, "model_name": "m1"},
        _clean_vndb_data,
    )
    assert req.role_name == "R"
    assert req.model_name == "m1"
    assert req.vndb_data["cleaned"] is True


def test_generate_character_card_request_checkpoint_io():
    req = GenerateCharacterCardRequest.from_payload(
        {
            "role_name": "R",
            "creator": "C",
            "vndb_data": {"img": "u"},
            "output_language": "en",
            "compression_mode": "llm",
            "force_no_compression": True,
            "resume_checkpoint_id": "x1",
            "model_name": "gpt",
        },
        _clean_vndb_data,
    )
    req.apply_checkpoint({"creator": "C2", "compression_mode": "original"})
    ckpt_input = req.to_checkpoint_input()
    assert ckpt_input["creator"] == "C2"
    assert ckpt_input["compression_mode"] == "original"
    assert "vndb_data_raw" in ckpt_input


def test_summarize_request_defaults_when_payload_missing():
    req = SummarizeRequest.from_payload({}, _clean_vndb_data, _extract_file_paths)
    assert req.role_name == ""
    assert req.instruction == ""
    assert req.concurrency == 1
    assert req.mode == "skills"
    assert req.resume_checkpoint_id is None
    assert req.output_language == ""
    assert req.vndb_data is None
    assert req.slice_size_k == 50
    assert req.file_paths == []


def test_summarize_request_apply_checkpoint_keeps_existing_when_missing_keys():
    req = SummarizeRequest(
        role_name="A",
        instruction="I",
        concurrency=3,
        mode="skills",
        output_language="zh",
        vndb_data={"k": 1},
        slice_size_k=100,
        file_paths=["a.txt"],
    )
    req.apply_checkpoint({})
    assert req.role_name == "A"
    assert req.instruction == "I"
    assert req.concurrency == 3
    assert req.slice_size_k == 100
    assert req.file_paths == ["a.txt"]


def test_generate_skills_request_defaults_and_checkpoint_behavior():
    req = GenerateSkillsRequest.from_payload({}, _clean_vndb_data)
    assert req.compression_mode == "original"
    assert req.force_no_compression is False
    assert req.model_name == ""
    req.apply_checkpoint({"compression_mode": "llm", "force_no_compression": True})
    ckpt_input = req.to_checkpoint_input()
    assert ckpt_input["compression_mode"] == "llm"
    assert ckpt_input["force_no_compression"] is True


def test_generate_character_card_request_model_name_and_raw_data():
    raw_vndb = {"id": 10}
    req = GenerateCharacterCardRequest.from_payload(
        {"vndb_data": raw_vndb, "model_name": "m-char"},
        _clean_vndb_data,
    )
    assert req.model_name == "m-char"
    assert req.vndb_data_raw == raw_vndb
    assert req.vndb_data == {"cleaned": True, "raw": raw_vndb}


def test_generate_requests_keep_backward_compatibility_for_modelname():
    skills_req = GenerateSkillsRequest.from_payload(
        {"modelname": "legacy-skills"},
        _clean_vndb_data,
    )
    card_req = GenerateCharacterCardRequest.from_payload(
        {"modelname": "legacy-card"},
        _clean_vndb_data,
    )

    assert skills_req.model_name == "legacy-skills"
    assert card_req.model_name == "legacy-card"
