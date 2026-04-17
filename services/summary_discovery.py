import os


def find_role_summary_markdown_files(base_dir, role_name):
    summary_files = []
    for root, dirs, files in os.walk(base_dir):
        for dir_name in dirs:
            if dir_name.endswith('_summaries'):
                summaries_dir = os.path.join(root, dir_name)
                for filename in sorted(os.listdir(summaries_dir)):
                    if filename.endswith('.md') and f'_{role_name}.md' in filename:
                        summary_files.append(os.path.join(summaries_dir, filename))
    return summary_files


def find_role_analysis_summary_file(base_dir, role_name):
    for root, dirs, files in os.walk(base_dir):
        for dir_name in dirs:
            if dir_name.endswith('_summaries'):
                summaries_dir = os.path.join(root, dir_name)
                summary_path = os.path.join(summaries_dir, f"{role_name}_analysis_summary.json")
                if os.path.exists(summary_path):
                    return summary_path
    return None
