import os
import sys
import tiktoken

class FileProcessor:
    def __init__(self):
        self.resource_dir = self._get_resource_dir()
        os.makedirs(self.resource_dir, exist_ok=True)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def _get_base_dir(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    def _get_resource_dir(self):
        return os.path.join(self._get_base_dir(), 'resource')
    
    def scan_resource_files(self):
        files = []
        if os.path.exists(self.resource_dir):
            for file in os.listdir(self.resource_dir):
                file_path = os.path.join(self.resource_dir, file)
                if os.path.isfile(file_path) and (file.endswith(".txt") or file.endswith(".md")):
                    files.append(file_path)
        return files
    
    @staticmethod
    def _read_text_as_utf8(file_path):
        encodings = ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gb18030")
        last_error = None
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                if encoding != "utf-8":
                    with open(file_path, 'w', encoding='utf-8', newline='') as f:
                        f.write(content)
                return content
            except UnicodeError as e:
                last_error = e
        if last_error:
            raise last_error
        raise UnicodeError("无法读取文件编码")
    
    def calculate_tokens(self, file_path):
        content = self._read_text_as_utf8(file_path)
        tokens = self.tokenizer.encode(content)
        return len(tokens)
    
    def calculate_slices(self, token_count, slice_size_k=50):
        slice_size = slice_size_k * 1000
        return (token_count // slice_size) + 1
    
    def slice_multiple_files(self, file_paths, slice_size_k=50):
        try:
            all_lines = []
            for file_path in file_paths:
                with open(file_path, 'r', encoding='utf-8') as f:
                    all_lines.extend(f.readlines())
            
            total_content = ''.join(all_lines)
            total_tokens = len(self.tokenizer.encode(total_content))
            slice_size = slice_size_k * 1000
            slice_count = (total_tokens // slice_size) + 1
            
            lines_per_slice = len(all_lines) // slice_count
            slices = []
            for i in range(slice_count):
                start_line = i * lines_per_slice
                end_line = (i + 1) * lines_per_slice if i < slice_count - 1 else len(all_lines)
                slice_content = ''.join(all_lines[start_line:end_line])
                slices.append(slice_content)
            return slices
        except Exception as e:
            return []

