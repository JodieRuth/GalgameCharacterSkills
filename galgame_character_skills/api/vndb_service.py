from ..domain import ok_result, fail_result


def fetch_vndb_character(vndb_id, r18_traits, vndb_gateway):
    vndb_id = (vndb_id or '').strip()
    if not vndb_id:
        return fail_result('未提供VNDB ID')

    char_id = vndb_id
    if vndb_id.lower().startswith('c'):
        char_id = vndb_id[1:]

    if not char_id.isdigit():
        return fail_result('无效的VNDB ID格式，应为 c+数字 或纯数字')

    try:
        response = vndb_gateway.query_character(char_id=char_id, timeout=10)

        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])

            if results and len(results) > 0:
                character = results[0]

                birthday = character.get('birthday', [])
                birthday_str = ""
                if birthday and len(birthday) >= 2:
                    birthday_str = f"{birthday[0]}/{birthday[1]}"
                traits = character.get('traits', [])
                trait_names = [t.get('name', '') for t in traits if t.get('name', '') not in r18_traits]

                vns = character.get('vns', [])
                vn_list = [v.get('title', '') for v in vns if v.get('title', '')]

                return ok_result(
                    data={
                        'vndb_id': vndb_id,
                        'name': character.get('name', ''),
                        'original_name': character.get('original', ''),
                        'aliases': character.get('aliases', []),
                        'description': character.get('description', ''),
                        'age': character.get('age', ''),
                        'birthday': birthday_str,
                        'blood_type': character.get('blood_type', ''),
                        'height': character.get('height', ''),
                        'weight': character.get('weight', ''),
                        'bust': character.get('bust', ''),
                        'waist': character.get('waist', ''),
                        'hips': character.get('hips', ''),
                        'image_url': character.get('image', {}).get('url', ''),
                        'traits': trait_names,
                        'vns': vn_list
                    }
                )
            return fail_result('未找到该角色')
        return fail_result(f'VNDB API请求失败: HTTP {response.status_code}')

    except TimeoutError:
        return fail_result('VNDB API请求超时')
    except Exception as e:
        return fail_result(f'获取VNDB信息失败: {str(e)}')
