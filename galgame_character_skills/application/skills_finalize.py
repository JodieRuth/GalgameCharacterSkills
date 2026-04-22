"""技能生成后处理模块，负责补充 VNDB 信息、复制代码技能并完成任务收尾。"""

import os
from typing import Any

from .app_container import TaskRuntimeDependencies
from .task_result_factory import ok_task_result
from ..domain import GenerateSkillsRequest
from ..skills import append_vndb_info_to_skill_md, create_code_skill_copy
from ..workspace import get_workspace_skills_dir


def finalize_generate_skills(
    request_data: GenerateSkillsRequest,
    checkpoint_id: str,
    all_results: list[Any],
    runtime: TaskRuntimeDependencies,
) -> dict[str, Any]:
    """完成技能生成任务。

    Args:
        request_data: 技能生成请求。
        checkpoint_id: checkpoint 标识。
        all_results: 已累积结果。
        runtime: 任务运行时依赖。

    Returns:
        dict[str, Any]: 统一任务结果。

    Raises:
        Exception: 后处理或落盘失败时向上抛出。
    """
    skills_root_dir = get_workspace_skills_dir()
    runtime.storage_gateway.makedirs(skills_root_dir, exist_ok=True)
    main_skill_dir = os.path.join(skills_root_dir, f"{request_data.role_name}-skill-main")
    skill_md_path = os.path.join(main_skill_dir, "SKILL.md")

    vndb_result = append_vndb_info_to_skill_md(skill_md_path, request_data.vndb_data)
    if vndb_result:
        all_results.append(vndb_result)

    copy_result = create_code_skill_copy(skills_root_dir, request_data.role_name)
    if copy_result:
        all_results.append(copy_result)

    runtime.checkpoint_gateway.mark_completed(checkpoint_id)
    return ok_task_result(
        message=f"技能文件夹生成完成，共执行 {len(all_results)} 次文件写入",
        results=all_results,
        checkpoint_id=checkpoint_id,
    )


__all__ = ["finalize_generate_skills"]
