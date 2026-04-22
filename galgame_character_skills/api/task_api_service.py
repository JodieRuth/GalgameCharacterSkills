"""任务接口模块，统一暴露 summarize、skills 与 character card 任务入口。"""

from typing import Any, Callable

from ..application.app_container import TaskRuntimeDependencies
from ..application.summarize_service import run_summarize_task
from ..application.skills_service import run_generate_skills_task
from ..application.character_card_service import run_generate_character_card_task
from .validators import require_non_empty_field


def summarize_result(
    data: dict[str, Any],
    runtime: TaskRuntimeDependencies,
) -> dict[str, Any]:
    """执行 summarize 任务接口。

    Args:
        data: 请求数据。
        runtime: 任务运行时依赖。

    Returns:
        dict[str, Any]: summarize 任务结果。

    Raises:
        Exception: 任务执行失败时向上抛出。
    """
    return run_summarize_task(
        data=data,
        runtime=runtime
    )


def generate_skills_folder_result(
    data: dict[str, Any],
    runtime: TaskRuntimeDependencies,
) -> dict[str, Any]:
    """执行技能包生成任务接口。

    Args:
        data: 请求数据。
        runtime: 任务运行时依赖。

    Returns:
        dict[str, Any]: 技能包生成结果。

    Raises:
        Exception: 任务执行失败时向上抛出。
    """
    return run_generate_skills_task(
        data=data,
        runtime=runtime
    )


def generate_character_card_result(
    data: dict[str, Any],
    runtime: TaskRuntimeDependencies,
) -> dict[str, Any]:
    """执行角色卡生成任务接口。

    Args:
        data: 请求数据。
        runtime: 任务运行时依赖。

    Returns:
        dict[str, Any]: 角色卡生成结果。

    Raises:
        Exception: 任务执行失败时向上抛出。
    """
    return run_generate_character_card_task(
        data=data,
        runtime=runtime
    )


@require_non_empty_field("role_name", "请输入角色名称")
def generate_skills_result(
    data: dict[str, Any],
    generate_skills_folder_handler: Callable[[dict[str, Any]], dict[str, Any]],
    generate_character_card_handler: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """按模式分发技能相关任务。

    Args:
        data: 请求数据。
        generate_skills_folder_handler: 技能包生成处理函数。
        generate_character_card_handler: 角色卡生成处理函数。

    Returns:
        dict[str, Any]: 分发后的任务结果。

    Raises:
        Exception: 任务分发或执行失败时向上抛出。
    """
    mode = data.get('mode', 'skills')

    if mode == 'chara_card':
        return generate_character_card_handler(data)
    return generate_skills_folder_handler(data)
