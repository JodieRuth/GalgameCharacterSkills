"""输入归一化模块，负责从多种请求形态中提取标准化文件路径列表。"""

def extract_file_paths(data):
    file_paths = data.get('file_paths', [])
    if not file_paths:
        single_file = data.get('file_path', '')
        if single_file:
            file_paths = [single_file]
    return file_paths
