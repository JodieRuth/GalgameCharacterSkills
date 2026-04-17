from ..application.summarize_service import run_summarize_task
from ..application.skills_service import run_generate_skills_task
from ..application.character_card_service import run_generate_character_card_task


def summarize_result(data, file_processor, ckpt_manager, clean_vndb_data):
    return run_summarize_task(
        data=data,
        file_processor=file_processor,
        ckpt_manager=ckpt_manager,
        clean_vndb_data=clean_vndb_data
    )


def generate_skills_folder_result(
    data,
    ckpt_manager,
    clean_vndb_data,
    get_base_dir,
    estimate_tokens,
    build_llm_client
):
    return run_generate_skills_task(
        data=data,
        ckpt_manager=ckpt_manager,
        clean_vndb_data=clean_vndb_data,
        get_base_dir=get_base_dir,
        estimate_tokens=estimate_tokens,
        build_llm_client=build_llm_client
    )


def generate_character_card_result(
    data,
    ckpt_manager,
    clean_vndb_data,
    get_base_dir,
    estimate_tokens,
    build_llm_client,
    download_vndb_image,
    embed_json_in_png
):
    return run_generate_character_card_task(
        data=data,
        ckpt_manager=ckpt_manager,
        clean_vndb_data=clean_vndb_data,
        get_base_dir=get_base_dir,
        estimate_tokens=estimate_tokens,
        build_llm_client=build_llm_client,
        download_vndb_image=download_vndb_image,
        embed_json_in_png=embed_json_in_png
    )


def generate_skills_result(data, generate_skills_folder_handler, generate_character_card_handler):
    role_name = data.get('role_name', '')
    mode = data.get('mode', 'skills')

    if not role_name:
        return {'success': False, 'message': '请输入角色名称'}

    if mode == 'chara_card':
        return generate_character_card_handler(data)
    return generate_skills_folder_handler(data)
