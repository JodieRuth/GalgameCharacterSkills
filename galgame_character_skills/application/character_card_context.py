"""角色卡上下文模块，负责分析数据加载与压缩。"""

import json
from typing import Any

from .app_container import TaskRuntimeDependencies
from .compression_policy import resolve_compression_policy
from .compression_executor import run_compression_pipeline
from .runtime_logging import log_message
from ..compression import compress_analyses_with_llm
from ..domain import GenerateCharacterCardRequest, fail_result
from ..files import find_role_analysis_summary_file


def load_character_analyses(
    runtime: TaskRuntimeDependencies,
    role_name: str,
) -> tuple[list[dict[str, Any]] | None, list[Any] | None, dict[str, Any] | None]:
    """加载角色分析数据。

    Args:
        runtime: 任务运行时依赖。
        role_name: 角色名。

    Returns:
        tuple[list[dict[str, Any]] | None, list[Any] | None, dict[str, Any] | None]:
            分析列表、lorebook 列表和错误结果。

    Raises:
        Exception: 文件读取异常未被内部拦截时向上抛出。
    """
    summaries_root_dir = runtime.get_workspace_summaries_dir()
    analysis_file = find_role_analysis_summary_file(summaries_root_dir, role_name)

    if not analysis_file:
        return None, None, fail_result(f'未找到角色 "{role_name}" 的分析文件，请先完成归纳')

    try:
        analysis_data = runtime.storage_gateway.read_json(analysis_file)
    except Exception as exc:
        return None, None, fail_result(f"读取分析文件失败: {str(exc)}")

    all_character_analyses = analysis_data.get("character_analyses", [])
    all_lorebook_entries = analysis_data.get("lorebook_entries", [])

    if not all_character_analyses:
        return None, None, fail_result("分析数据为空")

    return all_character_analyses, all_lorebook_entries, None


def compress_character_analyses(
    all_character_analyses: list[dict[str, Any]],
    request_data: GenerateCharacterCardRequest,
    config: dict[str, Any],
    checkpoint_id: str,
    runtime: TaskRuntimeDependencies,
) -> list[dict[str, Any]]:
    """压缩角色分析上下文。

    Args:
        all_character_analyses: 原始分析列表。
        request_data: 角色卡生成请求。
        config: LLM 配置。
        checkpoint_id: checkpoint 标识。
        runtime: 任务运行时依赖。

    Returns:
        list[dict[str, Any]]: 压缩后的分析列表。

    Raises:
        Exception: 压缩流程执行失败时向上抛出。
    """
    analyses_text = json.dumps(all_character_analyses, ensure_ascii=False)
    raw_estimated_tokens = runtime.estimate_tokens(analyses_text)
    policy = resolve_compression_policy(
        model_name=request_data.model_name,
        raw_estimated_tokens=raw_estimated_tokens,
        force_no_compression=request_data.force_no_compression,
    )

    def _llm_compress(target_budget_tokens: int) -> list[dict[str, Any]]:
        log_message("Using LLM compression for analyses", runtime=runtime)
        llm_interaction = runtime.llm_gateway.create_client(config)
        return compress_analyses_with_llm(
            analyses=all_character_analyses,
            llm_client=llm_interaction,
            target_budget_tokens=target_budget_tokens,
            checkpoint_id=checkpoint_id,
            ckpt_manager=runtime.checkpoint_gateway,
            estimate_tokens=runtime.estimate_tokens,
        )

    def _fallback_compress(target_budget_tokens: int) -> list[dict[str, Any]]:
        log_message("Using original compression", runtime=runtime)
        target_count = max(1, len(all_character_analyses) * target_budget_tokens // raw_estimated_tokens)
        return all_character_analyses[:target_count]

    compressed, used_compression, _, _ = run_compression_pipeline(
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
        all_character_analyses = compressed
        compressed_text = json.dumps(all_character_analyses, ensure_ascii=False)
        compressed_tokens = runtime.estimate_tokens(compressed_text)
        log_message(
            f"Compressed: {raw_estimated_tokens} -> {compressed_tokens} tokens "
            f"({compressed_tokens/raw_estimated_tokens*100:.1f}%)",
            runtime=runtime,
        )

    return all_character_analyses


__all__ = ["load_character_analyses", "compress_character_analyses"]
