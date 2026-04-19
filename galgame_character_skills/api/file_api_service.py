from ..domain import ok_result, fail_result


def scan_files_result(file_processor):
    files = file_processor.scan_resource_files()
    return ok_result(files=files)


def upload_files_result(file_processor, files):
    if not files:
        return fail_result('请先选择要上传的文件')
    try:
        saved_files = file_processor.save_uploaded_files(files)
        if not saved_files:
            return fail_result('未检测到可上传的 .txt/.md 文件')
        return ok_result(
            message=f'上传完成，共保存 {len(saved_files)} 个文件',
            files=saved_files,
        )
    except Exception as e:
        return fail_result(f'上传失败: {str(e)}')


def calculate_tokens_result(file_processor, data):
    file_path = data.get('file_path', '')
    slice_size_k = data.get('slice_size_k', 50)
    if not file_path:
        return fail_result('未提供文件路径')
    try:
        token_count = file_processor.calculate_tokens(file_path)
        slice_count = file_processor.calculate_slices(token_count, slice_size_k)
        return ok_result(
            token_count=token_count,
            slice_count=slice_count,
            formatted_tokens=f"{token_count:,}"
        )
    except Exception as e:
        return fail_result(str(e))


def slice_file_result(file_processor, data, extract_file_paths):
    slice_size_k = data.get('slice_size_k', 50)
    file_paths = extract_file_paths(data)

    if not file_paths:
        return fail_result('请先选择文件')

    try:
        slices = file_processor.slice_multiple_files(file_paths, slice_size_k)
        file_count = len(file_paths)
        return ok_result(
            message=f'已合并 {file_count} 个文件并切片，共 {len(slices)} 个切片',
            slice_count=len(slices),
            file_count=file_count
        )
    except Exception as e:
        return fail_result(f'切片失败: {str(e)}')
