from types import SimpleNamespace

from galgame_character_skills.application.shared.task_state import (
    SkillsResumeState,
    CharacterCardResumeState,
    build_initial_state_factory,
    build_resume_state_loader,
)


def test_build_initial_state_factory_returns_default_state_instance():
    factory = build_initial_state_factory(SkillsResumeState)
    state = factory()

    assert isinstance(state, SkillsResumeState)
    assert state.messages == []
    assert state.all_results == []
    assert state.iteration == 0


def test_build_resume_state_loader_maps_llm_fields():
    loader = build_resume_state_loader(
        SkillsResumeState,
        {
            "messages": "messages",
            "all_results": "all_results",
            "iteration": "iteration_count",
        },
    )
    gateway = SimpleNamespace(
        load_llm_state=lambda _checkpoint_id: {
            "messages": ["m1"],
            "all_results": ["r1"],
            "iteration_count": 3,
        }
    )
    state = loader(gateway, "ckpt-1", {})

    assert state.messages == ["m1"]
    assert state.all_results == ["r1"]
    assert state.iteration == 3


def test_build_resume_state_loader_falls_back_to_state_defaults():
    loader = build_resume_state_loader(
        CharacterCardResumeState,
        {
            "fields_data": "fields_data",
            "messages": "messages",
            "iteration_count": "iteration_count",
        },
    )
    gateway = SimpleNamespace(load_llm_state=lambda _checkpoint_id: {"messages": ["keep"]})
    state = loader(gateway, "ckpt-2", {})

    assert state.fields_data == {}
    assert state.messages == ["keep"]
    assert state.iteration_count == 0
