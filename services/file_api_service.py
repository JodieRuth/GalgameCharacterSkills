def scan_files_result(file_processor):
    files = file_processor.scan_resource_files()
    return {'success': True, 'files': files}


def calculate_tokens_result(file_processor, data):
    file_path = data.get('file_path', '')
    slice_size_k = data.get('slice_size_k', 50)
    if not file_path:
        return {'success': False, 'message': '未提供文件路径'}
    try:
        token_count = file_processor.calculate_tokens(file_path)
        slice_count = file_processor.calculate_slices(token_count, slice_size_k)
        return {
            'success': True,
            'token_count': token_count,
            'slice_count': slice_count,
            'formatted_tokens': f"{token_count:,}"
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}


def slice_file_result(file_processor, data, extract_file_paths):
    slice_size_k = data.get('slice_size_k', 50)
    file_paths = extract_file_paths(data)

    if not file_paths:
        return {'success': False, 'message': '请先选择文件'}

    try:
        slices = file_processor.slice_multiple_files(file_paths, slice_size_k)
        file_count = len(file_paths)
        return {
            'success': True,
            'message': f'已合并 {file_count} 个文件并切片，共 {len(slices)} 个切片',
            'slice_count': len(slices),
            'file_count': file_count
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'切片失败: {str(e)}'
        }
