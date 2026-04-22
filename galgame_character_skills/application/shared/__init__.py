"""应用层共享模块。"""

from .checkpoint_prepare import PreparedCheckpointData, prepare_request_with_checkpoint
from .runtime_logging import get_logger, log_message
from .task_prepared import (
    BasePreparedTask,
    PreparedGenerateCharacterCardTask,
    PreparedGenerateSkillsTask,
    PreparedSummarizeTask,
)
from .task_prepare_context import (
    build_basic_prepared_builder,
    build_clean_payload_loader,
    build_on_resumed_logger,
    build_prepared_state_builder,
    chain_on_resumed,
    prepare_task_context,
)
from .task_result_factory import build_dataclass_result_mapper, fail_task_result, ok_task_result
from .task_state import (
    CharacterCardResumeState,
    SkillsResumeState,
    SummarizeResumeState,
    build_initial_state_factory,
    build_resume_state_loader,
)

__all__ = [
    "BasePreparedTask",
    "CharacterCardResumeState",
    "PreparedCheckpointData",
    "PreparedGenerateCharacterCardTask",
    "PreparedGenerateSkillsTask",
    "PreparedSummarizeTask",
    "SkillsResumeState",
    "SummarizeResumeState",
    "build_basic_prepared_builder",
    "build_clean_payload_loader",
    "build_dataclass_result_mapper",
    "build_initial_state_factory",
    "build_on_resumed_logger",
    "build_prepared_state_builder",
    "build_resume_state_loader",
    "chain_on_resumed",
    "fail_task_result",
    "get_logger",
    "log_message",
    "ok_task_result",
    "prepare_request_with_checkpoint",
    "prepare_task_context",
]
