from ..application.summarize_service import run_summarize_task
from ..application.skills_service import run_generate_skills_task
from ..application.character_card_service import run_generate_character_card_task


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


def generate_skills_result(data, generate_skills_folder_handler, generate_character_card_handler):
    role_name = data.get('role_name', '')
    mode = data.get('mode', 'skills')

    if not role_name:
        return {'success': False, 'message': '请输入角色名称'}

    if mode == 'chara_card':
        return generate_character_card_handler(data)
    return generate_skills_folder_handler(data)
