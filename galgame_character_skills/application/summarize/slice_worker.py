"""summarize 单切片执行模块。"""

import time
from typing import Any, Callable

from ..shared.runtime_logging import log_message
from .checkpoint import persist_slice_checkpoint_if_needed
from .models import SliceExecutionResult, SliceTask, to_slice_task
from .slice_finalize import (
    build_restored_slice_result,
    handle_chara_card_slice_choice,
    handle_skills_slice_choice,
)
from ...llm.message_flows import send_summarize_chara_card_content, send_summarize_content
from ...llm.shared import LANG_NAMES, format_vndb_section


def _restore_slice_if_possible(
    task: SliceTask,
    checkpoint_gateway: Any,
    storage_gateway: Any,
    logger: Callable[[str], None] | None = None,
) -> SliceExecutionResult | None:
    checkpoint_id = task.checkpoint_id
    if not checkpoint_id:
        return None

    existing = checkpoint_gateway.get_slice_result(checkpoint_id, task.slice_index)
    if not existing:
        return None

    log_message(f"Slice {task.slice_index} already completed, skipping", logger=logger)
    return build_restored_slice_result(
        slice_index=task.slice_index,
        mode=task.mode,
        output_file_path=task.output_file_path,
        storage_gateway=storage_gateway,
    )


def _send_slice_request(task: SliceTask, llm_client: Any) -> Any:
    if task.mode == "chara_card":
        return send_summarize_chara_card_content(
            send_message=llm_client.send_message,
            lang_names=LANG_NAMES,
            format_vndb_section=format_vndb_section,
            content=task.slice_content,
            role_name=task.role_name,
            instruction=task.instruction,
            output_file_path=task.output_file_path,
            output_language=task.output_language,
            vndb_data=task.vndb_data,
        )
    return send_summarize_content(
        send_message=llm_client.send_message,
        lang_names=LANG_NAMES,
        format_vndb_section=format_vndb_section,
        content=task.slice_content,
        role_name=task.role_name,
        instruction=task.instruction,
        output_file_path=task.output_file_path,
        output_language=task.output_language,
        vndb_data=task.vndb_data,
    )


def process_single_slice(
    args: SliceTask | tuple[Any, ...],
    checkpoint_gateway: Any,
    llm_gateway: Any,
    tool_gateway: Any,
    storage_gateway: Any,
    request_runtime: Any = None,
    logger: Callable[[str], None] | None = None,
) -> SliceExecutionResult:
    """执行单个切片归纳。"""
    task = to_slice_task(args)
    restored = _restore_slice_if_possible(task, checkpoint_gateway, storage_gateway, logger=logger)
    if restored is not None:
        return restored

    llm_client = llm_gateway.create_client(task.config, request_runtime=request_runtime)
    time.sleep(0.5 * task.slice_index)
    response = _send_slice_request(task, llm_client)

    result = SliceExecutionResult(index=task.slice_index, output_path=task.output_file_path)
    choice = None

    if response and hasattr(response, "choices") and response.choices:
        choice = response.choices[0]
        if task.mode == "chara_card":
            handle_chara_card_slice_choice(
                result=result,
                choice=choice,
                output_file_path=task.output_file_path,
                tool_gateway=tool_gateway,
                storage_gateway=storage_gateway,
            )
        else:
            handle_skills_slice_choice(
                result=result,
                choice=choice,
                output_file_path=task.output_file_path,
                tool_gateway=tool_gateway,
                storage_gateway=storage_gateway,
            )

    if choice is not None:
        persist_slice_checkpoint_if_needed(
            checkpoint_id=task.checkpoint_id,
            slice_index=task.slice_index,
            mode=task.mode,
            output_file_path=task.output_file_path,
            choice=choice,
            result=result,
            checkpoint_gateway=checkpoint_gateway,
            storage_gateway=storage_gateway,
            logger=logger,
        )

    return result


__all__ = ["process_single_slice"]
