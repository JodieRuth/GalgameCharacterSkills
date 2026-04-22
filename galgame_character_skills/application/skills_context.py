"""技能生成上下文模块，负责汇总 summary 与执行上下文压缩。"""

from dataclasses import dataclass
from typing import Any

from .app_container import TaskRuntimeDependencies
from .compression_policy import resolve_compression_policy
from .compression_executor import run_compression_pipeline
from .runtime_logging import log_message
from ..compression import compress_summary_files_with_llm
from ..domain import GenerateSkillsRequest, fail_result
from ..skills import (
    build_full_skill_generation_context,
    build_prioritized_skill_generation_context,
)


@dataclass(frozen=True)
class SkillsContextData:
    """技能生成上下文结果模型。

    用于封装最终送入技能生成流程的上下文文本及其来源模式。
    """

    summaries_text: str
    context_mode: str

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


def build_skill_context(
    summary_files: list[str],
    request_data: GenerateSkillsRequest,
    config: dict[str, Any],
    checkpoint_id: str,
    runtime: TaskRuntimeDependencies,
) -> tuple[SkillsContextData | None, dict[str, Any] | None]:
    """构建技能生成上下文。

    Args:
        summary_files: summary 文件路径列表。
        request_data: 技能生成请求。
        config: LLM 配置。
        checkpoint_id: checkpoint 标识。
        runtime: 任务运行时依赖。

    Returns:
        tuple[SkillsContextData | None, dict[str, Any] | None]: 上下文数据和错误结果。

    Raises:
        Exception: 上下文构建或压缩失败时向上抛出。
    """
    raw_full_text = build_full_skill_generation_context(summary_files)
    raw_total_chars = len(raw_full_text)
    raw_estimated_tokens = runtime.estimate_tokens(raw_full_text)
    policy = resolve_compression_policy(
        model_name=request_data.model_name,
        raw_estimated_tokens=raw_estimated_tokens,
        force_no_compression=request_data.force_no_compression,
    )
    context_mode = "full"
    summaries_text = raw_full_text

    def _llm_compress(target_budget_tokens: int) -> str:
        log_message("Using LLM compression", runtime=runtime)
        llm_interaction = runtime.llm_gateway.create_client(config)
        return compress_summary_files_with_llm(
            summary_files=summary_files,
            llm_client=llm_interaction,
            target_budget_tokens=target_budget_tokens,
            checkpoint_id=checkpoint_id,
            ckpt_manager=runtime.checkpoint_gateway,
            estimate_tokens=runtime.estimate_tokens,
        )

    def _fallback_compress(target_budget_tokens: int) -> str:
        log_message("Using original compression", runtime=runtime)
        target_budget_chars = target_budget_tokens * 2
        return build_prioritized_skill_generation_context(
            summary_files,
            target_total_chars=target_budget_chars,
        )

    compressed, used_compression, _context_limit, _context_limit_tokens = run_compression_pipeline(
        runtime=runtime,
        model_name=request_data.model_name,
        compression_mode=request_data.compression_mode,
        force_no_compression=request_data.force_no_compression,
        raw_estimated_tokens=raw_estimated_tokens,
        policy=policy,
        llm_compress=_llm_compress,
        fallback_compress=_fallback_compress,
    )
    if used_compression:
        summaries_text = compressed
        context_mode = "llm_compressed" if request_data.compression_mode == "llm" else "compressed"
    elif policy["force_exceeds_limit"]:
        context_mode = "full_forced"

    if not summaries_text:
        return None, fail_result(f'未能读取角色 "{request_data.role_name}" 的归纳内容')

    compressed_chars = len(summaries_text)
    estimated_tokens = runtime.estimate_tokens(summaries_text)
    compression_ratio = (compressed_chars / raw_total_chars) if raw_total_chars else 0
    strategy_name = {
        "full": "full_context",
        "full_forced": "full_context_no_compression",
        "compressed": "head_tail_weighted_1_2_then_key_sections",
        "llm_compressed": "llm_deduplication",
    }.get(context_mode, "unknown")

    log_message(
        f"role={request_data.role_name} files={len(summary_files)} mode={context_mode} "
        f"raw_chars={raw_total_chars} raw_estimated_tokens={raw_estimated_tokens} "
        f"final_chars={compressed_chars} final_estimated_tokens={estimated_tokens} "
        f"compression_ratio={compression_ratio:.2%} "
        f"strategy={strategy_name}",
        runtime=runtime,
    )

    return SkillsContextData(
        summaries_text=summaries_text,
        context_mode=context_mode,
    ), None


__all__ = ["SkillsContextData", "build_skill_context"]
