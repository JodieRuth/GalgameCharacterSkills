"""任务恢复状态模块，定义不同任务类型的 resume state 与加载器工厂。"""

from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar


@dataclass(frozen=True)
class SkillsResumeState:
    messages: list = field(default_factory=list)
    all_results: list = field(default_factory=list)
    iteration: int = 0


@dataclass(frozen=True)
class CharacterCardResumeState:
    fields_data: dict = field(default_factory=dict)
    messages: list = field(default_factory=list)
    iteration_count: int = 0


@dataclass(frozen=True)
class SummarizeResumeState:
    checkpoint: dict


StateT = TypeVar("StateT")


def build_initial_state_factory(state_cls: type[StateT]) -> Callable[[], StateT]:
    return state_cls


def build_resume_state_loader(
    state_cls: type[StateT],
    llm_field_map: dict[str, str],
) -> Callable[[Any, str, dict], StateT]:
    default_state = state_cls()

    def loader(checkpoint_gateway, checkpoint_id, _checkpoint):
        llm_state = checkpoint_gateway.load_llm_state(checkpoint_id)
        state_kwargs = {
            field_name: llm_state.get(llm_key, getattr(default_state, field_name))
            for field_name, llm_key in llm_field_map.items()
        }
        return state_cls(**state_kwargs)

    return loader


__all__ = [
    "SkillsResumeState",
    "CharacterCardResumeState",
    "SummarizeResumeState",
    "build_initial_state_factory",
    "build_resume_state_loader",
]
