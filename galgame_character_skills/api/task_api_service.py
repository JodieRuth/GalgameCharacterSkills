"""任务接口模块，统一暴露 summarize、skills 与 character card 任务入口。"""

from ..application.summarize_service import run_summarize_task
from ..application.skills_service import run_generate_skills_task
from ..application.character_card_service import run_generate_character_card_task
from .validators import require_non_empty_field


def summarize_result(data, runtime):
    return run_summarize_task(
        data=data,
        runtime=runtime
    )


def generate_skills_folder_result(data, runtime):
    return run_generate_skills_task(
        data=data,
        runtime=runtime
    )


def generate_character_card_result(data, runtime):
    return run_generate_character_card_task(
        data=data,
        runtime=runtime
    )


@require_non_empty_field("role_name", "请输入角色名称")
def generate_skills_result(data, generate_skills_folder_handler, generate_character_card_handler):
    mode = data.get('mode', 'skills')

    if mode == 'chara_card':
        return generate_character_card_handler(data)
    return generate_skills_folder_handler(data)
