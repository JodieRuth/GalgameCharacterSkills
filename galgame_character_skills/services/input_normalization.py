def extract_file_paths(data):
    file_paths = data.get('file_paths', [])
    if not file_paths:
        single_file = data.get('file_path', '')
        if single_file:
            file_paths = [single_file]
    return file_paths
