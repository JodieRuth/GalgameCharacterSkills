from dataclasses import dataclass, field

from galgame_character_skills.application.shared.task_result_factory import build_dataclass_result_mapper


@dataclass(frozen=True)
class _ResultModel:
    success: bool
    message: str = ""
    items: list = field(default_factory=list)
    count: int = 0


def test_build_dataclass_result_mapper_applies_field_transformers():
    mapper = build_dataclass_result_mapper(
        _ResultModel,
        {
            "success": bool,
            "message": lambda v: (v or "").strip(),
            "count": lambda v: int(v or 0),
        },
    )

    result = mapper({"success": 1, "message": "  ok  ", "count": "3"})

    assert result.success is True
    assert result.message == "ok"
    assert result.count == 3


def test_build_dataclass_result_mapper_uses_defaults_when_missing():
    mapper = build_dataclass_result_mapper(
        _ResultModel,
        {
            "success": bool,
        },
    )

    result = mapper({"success": 0})

    assert result.success is False
    assert result.message == ""
    assert result.items == []
    assert result.count == 0


def test_build_dataclass_result_mapper_handles_none_input():
    mapper = build_dataclass_result_mapper(
        _ResultModel,
        {
            "success": bool,
        },
    )

    result = mapper(None)

    assert result.success is False
    assert result.message == ""
    assert result.items == []
    assert result.count == 0
