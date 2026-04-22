"""summarize 切片执行模块，负责单片处理、结果落盘与并发调度。"""

import json
import time
from concurrent.futures import as_completed
from dataclasses import dataclass
from typing import Any, Callable

from .app_container import TaskRuntimeDependencies
from .runtime_logging import log_message
from .summarize_checkpoint import persist_slice_checkpoint_if_needed
from ..llm.message_flows import send_summarize_content, send_summarize_chara_card_content
from ..llm.shared import LANG_NAMES, format_vndb_section


@dataclass(frozen=True)
class SliceTask:
    """切片任务模型。

    用于描述单个切片在执行阶段所需的全部输入信息。
    """

    slice_index: int
    slice_content: str
    role_name: str
    instruction: str
    output_file_path: str
    config: dict
    output_language: str
    mode: str
    vndb_data: object
    checkpoint_id: str | None


@dataclass
class SliceExecutionResult:
    """单个切片执行结果模型。

    统一封装切片执行后的摘要文本、工具结果与恢复状态。
    """

    index: int
    success: bool = False
    summary: str | None = None
    tool_results: list = None
    output_path: str = ""
    character_analysis: dict | None = None
    lorebook_entries: list = None
    restored: bool = False

    def __post_init__(self):
        """初始化默认集合字段。

        Args:
            None

        Returns:
            None

        Raises:
            Exception: 默认值初始化失败时向上抛出。
        """
        if self.tool_results is None:
            self.tool_results = []
        if self.lorebook_entries is None:
            self.lorebook_entries = []

    def __getitem__(self, key):
        """提供兼容字典式读取的访问方式。

        Args:
            key: 字段名。

        Returns:
            Any: 对应字段值。

        Raises:
            AttributeError: 字段不存在时抛出。
        """
        return getattr(self, key)

    def get(self, key, default=None):
        """提供兼容字典式读取的安全访问方式。

        Args:
            key: 字段名。
            default: 字段不存在时返回的默认值。

        Returns:
            Any: 对应字段值或默认值。

        Raises:
            Exception: 字段访问失败时向上抛出。
        """
        return getattr(self, key, default)


@dataclass
class SummarizeExecutionAggregate:
    """summarize 并发执行聚合结果。

    用于累积所有切片的摘要、错误、工具结果与分析数据。
    """

    summaries: list = None
    errors: list = None
    all_results: list = None
    all_character_analyses: list = None
    all_lorebook_entries: list = None

    def __post_init__(self):
        """初始化默认聚合集合字段。

        Args:
            None

        Returns:
            None

        Raises:
            Exception: 默认值初始化失败时向上抛出。
        """
        if self.summaries is None:
            self.summaries = []
        if self.errors is None:
            self.errors = []
        if self.all_results is None:
            self.all_results = []
        if self.all_character_analyses is None:
            self.all_character_analyses = []
        if self.all_lorebook_entries is None:
            self.all_lorebook_entries = []


def to_slice_task(args: SliceTask | tuple[Any, ...]) -> SliceTask:
    """将切片参数归一化为任务对象。

    Args:
        args: 切片任务对象或其元组形式。

    Returns:
        SliceTask: 归一化后的切片任务。

    Raises:
        ValueError: 元组结构不符合预期时抛出。
    """
    if isinstance(args, SliceTask):
        return args

    (
        slice_index,
        slice_content,
        role_name,
        instruction,
        output_file_path,
        config,
        output_language,
        mode,
        vndb_data,
        checkpoint_id,
    ) = args
    return SliceTask(
        slice_index=slice_index,
        slice_content=slice_content,
        role_name=role_name,
        instruction=instruction,
        output_file_path=output_file_path,
        config=config,
        output_language=output_language,
        mode=mode,
        vndb_data=vndb_data,
        checkpoint_id=checkpoint_id,
    )


def extract_write_file_content(choice: Any) -> str:
    """提取 write_file 工具中的文本内容。

    Args:
        choice: LLM 返回选择项。

    Returns:
        str: write_file 中的 content 字段。

    Raises:
        Exception: 工具参数解析异常未被内部拦截时向上抛出。
    """
    if not (hasattr(choice, "message") and hasattr(choice.message, "tool_calls") and choice.message.tool_calls):
        return ""
    for tool_call in choice.message.tool_calls:
        if hasattr(tool_call, "function") and tool_call.function.name == "write_file":
            try:
                args_dict = json.loads(tool_call.function.arguments)
            except Exception:
                return ""
            return args_dict.get("content", "") or ""
    return ""


def finalize_skills_slice_result(
    result: SliceExecutionResult,
    choice: Any,
    output_file_path: str,
    storage_gateway: Any,
) -> None:
    """完成 skills 模式切片结果落盘。

    Args:
        result: 切片执行结果。
        choice: LLM 返回选择项。
        output_file_path: 切片输出路径。
        storage_gateway: 存储网关。

    Returns:
        None

    Raises:
        Exception: 文件写入失败时向上抛出。
    """
    content_from_tool = extract_write_file_content(choice)
    content = content_from_tool or (result.summary or "")
    if not content.strip():
        result.success = False
        result.summary = None
        result.tool_results.append("Empty summary content")
        return

    if not content_from_tool:
        storage_gateway.write_text(output_file_path, content)
        result.summary = content

    if not storage_gateway.exists(output_file_path):
        result.success = False
        result.summary = None
        result.tool_results.append("Summary file was not saved")


def process_single_slice(
    args: SliceTask | tuple[Any, ...],
    checkpoint_gateway: Any,
    llm_gateway: Any,
    tool_gateway: Any,
    storage_gateway: Any,
    request_runtime: Any = None,
    logger: Callable[[str], None] | None = None,
) -> SliceExecutionResult:
    """执行单个切片归纳。

    Args:
        args: 切片任务对象或其元组形式。
        checkpoint_gateway: checkpoint 网关。
        llm_gateway: LLM 网关。
        tool_gateway: 工具网关。
        storage_gateway: 存储网关。
        request_runtime: 请求级 LLM 运行时。
        logger: 日志函数。

    Returns:
        SliceExecutionResult: 切片执行结果。

    Raises:
        Exception: 切片处理异常未被内部拦截时向上抛出。
    """
    task = to_slice_task(args)
    slice_index = task.slice_index
    output_file_path = task.output_file_path
    mode = task.mode
    checkpoint_id = task.checkpoint_id
    llm_client = llm_gateway.create_client(task.config, request_runtime=request_runtime)

    if checkpoint_id:
        existing = checkpoint_gateway.get_slice_result(checkpoint_id, slice_index)
        if existing:
            log_message(f"Slice {slice_index} already completed, skipping", logger=logger)
            result = SliceExecutionResult(
                index=slice_index,
                success=True,
                summary=f"Slice {slice_index + 1} restored from checkpoint",
                output_path=output_file_path,
                restored=True,
            )
            if mode == "chara_card":
                try:
                    if not storage_gateway.exists(output_file_path):
                        return result
                    parsed = storage_gateway.read_json(output_file_path)
                    result.character_analysis = parsed.get("character_analysis", {})
                    result.lorebook_entries = parsed.get("lorebook_entries", [])
                except Exception:
                    pass
            else:
                try:
                    if not storage_gateway.exists(output_file_path):
                        return result
                    content = storage_gateway.read_text(output_file_path)
                    result.summary = content[:200] + "..." if len(content) > 200 else content
                except Exception:
                    pass
            return result

    time.sleep(0.5 * slice_index)

    if mode == "chara_card":
        response = send_summarize_chara_card_content(
            send_message=llm_client.send_message,
            lang_names=LANG_NAMES,
            format_vndb_section=format_vndb_section,
            content=task.slice_content,
            role_name=task.role_name,
            instruction=task.instruction,
            output_file_path=output_file_path,
            output_language=task.output_language,
            vndb_data=task.vndb_data,
        )
    else:
        response = send_summarize_content(
            send_message=llm_client.send_message,
            lang_names=LANG_NAMES,
            format_vndb_section=format_vndb_section,
            content=task.slice_content,
            role_name=task.role_name,
            instruction=task.instruction,
            output_file_path=output_file_path,
            output_language=task.output_language,
            vndb_data=task.vndb_data,
        )

    result = SliceExecutionResult(index=slice_index, output_path=output_file_path)
    choice = None

    if response and hasattr(response, "choices") and response.choices:
        choice = response.choices[0]

        if mode == "chara_card":
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    tool_result = tool_gateway.handle_tool_call(tool_call)
                    result.tool_results.append(tool_result)
                result.success = True
                result.summary = f"Slice {slice_index + 1} saved to {output_file_path}"

                try:
                    parsed = storage_gateway.read_json(output_file_path)
                    result.character_analysis = parsed.get("character_analysis", {})
                    result.lorebook_entries = parsed.get("lorebook_entries", [])
                except Exception as exc:
                    result.tool_results.append(f"Warning: Failed to read saved file: {exc}")

            elif hasattr(choice, "message") and choice.message.content:
                content = choice.message.content
                parsed = tool_gateway.parse_llm_json_response(content)
                if parsed:
                    result.character_analysis = parsed.get("character_analysis", {})
                    result.lorebook_entries = parsed.get("lorebook_entries", [])
                    result.success = True
                    result.summary = f"Slice {slice_index + 1} analyzed successfully"
                    storage_gateway.write_json(output_file_path, parsed, ensure_ascii=False, indent=2)
        else:
            if hasattr(choice, "message") and hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    tool_result = tool_gateway.handle_tool_call(tool_call)
                    result.tool_results.append(tool_result)
                result.success = True
                result.summary = f"Slice {slice_index + 1} saved to {output_file_path}"
            else:
                result.success = True
                result.summary = choice.message.content
            finalize_skills_slice_result(result, choice, output_file_path, storage_gateway)

    if choice is not None:
        persist_slice_checkpoint_if_needed(
            checkpoint_id=checkpoint_id,
            slice_index=slice_index,
            mode=mode,
            output_file_path=output_file_path,
            choice=choice,
            result=result,
            checkpoint_gateway=checkpoint_gateway,
            storage_gateway=storage_gateway,
            logger=logger,
        )

    return result


def execute_slice_tasks(
    tasks: list[SliceTask],
    request_data: Any,
    runtime: TaskRuntimeDependencies,
    request_runtime: Any = None,
) -> SummarizeExecutionAggregate:
    """并发执行切片任务。

    Args:
        tasks: 切片任务列表。
        request_data: 归纳请求。
        runtime: 任务运行时依赖。
        request_runtime: 请求级 LLM 运行时。

    Returns:
        SummarizeExecutionAggregate: 归纳执行汇总结果。

    Raises:
        Exception: 线程池执行异常未被内部拦截时向上抛出。
    """
    execution = SummarizeExecutionAggregate()

    with runtime.executor_gateway.create(max_workers=request_data.concurrency) as executor:
        future_to_task = {
            executor.submit(
                process_single_slice,
                task,
                runtime.checkpoint_gateway,
                runtime.llm_gateway,
                runtime.tool_gateway,
                runtime.storage_gateway,
                request_runtime,
                runtime.log,
            ): task
            for task in tasks
        }

        for future in as_completed(future_to_task):
            try:
                result = future.result()
                if result.success:
                    execution.summaries.append(result.summary)
                    execution.all_results.extend(result.tool_results)
                    if result.character_analysis:
                        execution.all_character_analyses.append(result.character_analysis)
                    if result.lorebook_entries:
                        execution.all_lorebook_entries.append(result.lorebook_entries)
                else:
                    execution.errors.append(f"切片 {result.index + 1} 处理失败")
            except Exception as exc:
                task = future_to_task[future]
                execution.errors.append(f"切片 {task.slice_index + 1} 处理异常: {str(exc)}")

    return execution


__all__ = [
    "SliceTask",
    "SliceExecutionResult",
    "SummarizeExecutionAggregate",
    "to_slice_task",
    "extract_write_file_content",
    "finalize_skills_slice_result",
    "process_single_slice",
    "execute_slice_tasks",
]
