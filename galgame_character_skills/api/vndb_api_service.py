def get_vndb_info_result(data, r18_traits, vndb_gateway, fetch_vndb_character):
    vndb_id = data.get('vndb_id', '')
    return fetch_vndb_character(vndb_id, r18_traits, vndb_gateway)
