"""character_card 相关 prompt 模块。"""

from typing import Any


def build_compress_content_payload(
    group_files_content: dict[str, str],
    group_info: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """构造压缩请求载荷。"""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "remove_duplicate_sections",
                "description": "Remove duplicate sections from files by specifying the exact filename and content to remove. The tool will find and remove the first occurrence of the specified content in the corresponding file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_sections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "filename": {
                                        "type": "string",
                                        "description": "The filename where the duplicate content is located (e.g., 'summary_001.md')",
                                    },
                                    "content": {
                                        "type": "string",
                                        "description": "The exact duplicate content section to be removed. Must match the content in the file exactly.",
                                    },
                                },
                                "required": ["filename", "content"],
                            },
                            "description": "List of duplicate sections to remove, each containing filename and the exact content to remove",
                        }
                    },
                    "required": ["file_sections"],
                },
            },
        }
    ]

    system_prompt = """You are an aggressive text deduplication assistant. Your task is to analyze multiple summary files and identify ALL duplicate content for maximum compression.

## Guidelines:
1. Analyze content across ALL files in the group thoroughly
2. Identify ANY sections that contain the same information, even if phrased slightly differently
3. Mark ALL duplicate sections for removal from later files
4. Focus on: character descriptions, events, relationships, personality traits, speech patterns
5. If the same information appears in multiple files, it IS a duplicate

## How to use the tool:
1. Read through all files in the group
2. Identify ALL duplicate sections (same information appearing in multiple files)
3. For each duplicate:
   - Keep the first occurrence (in the earliest file)
   - Mark ALL subsequent occurrences for removal
4. Call remove_duplicate_sections with a list of {filename, content} objects
   - filename: the file where the duplicate appears
   - content: the exact duplicate text to remove

## Important:
- The "content" field must match EXACTLY what's in the file (character for character)
- Remove ALL duplicates aggressively - we want maximum compression
- If information appears in File 1 and File 2, remove it from File 2
- If information appears in File 1, File 3, and File 5, remove it from File 3 and File 5
- JSON and Markdown files are handled the same way - match exact text
- BE AGGRESSIVE - mark every duplicate you find
- FORMAT DOES NOT MATTER - removing content may break file structure, that's OK
- The remaining content will be reprocessed later, so only semantic uniqueness matters"""

    files_display = []
    for idx, (filename, content) in enumerate(group_files_content.items()):
        files_display.append(f"\n{'='*60}\nFILE {idx + 1}: {filename}\n{'='*60}\n{content}")

    all_content = "\n".join(files_display)

    user_prompt = f"""Please analyze the following {len(group_files_content)} files and identify ALL duplicate sections for aggressive compression.

## Group Information:
- This is group {group_info['group_index'] + 1} of {group_info['total_groups']}
- Total files in this group: {group_info['file_count']}
- Files are shown in order (File 1 is the earliest, File N is the latest)

## Files to Analyze:
{all_content}

## Instructions:
1. Compare content across ALL files thoroughly
2. Identify EVERY section that appears in multiple files (even partially)
3. For each duplicate section:
   - Keep it ONLY in the earliest file where it appears
   - Mark it for removal in ALL later files
4. **BATCH REMOVAL**: You can remove duplicates in multiple rounds. You DON'T need to find all duplicates in one call.
   - In each round, mark some duplicates for removal
   - After processing, you will see the updated files
   - Continue with another round if there are still duplicates
   - This allows for more thorough compression
5. Use the remove_duplicate_sections tool with format:
   {{
     "file_sections": [
       {{"filename": "file2.md", "content": "exact duplicate text from file2"}},
       {{"filename": "file3.md", "content": "exact duplicate text from file3"}},
       {{"filename": "file4.md", "content": "exact duplicate text from file4"}}
     ]
   }}

## Important Notes:
- The "content" must match EXACTLY (character for character)
- Remove ALL duplicates - be AGGRESSIVE
- If content appears in File 1 and File 2, REMOVE from File 2
- If content appears in 5 files, keep only in File 1, remove from Files 2-5
- Look for: character descriptions, events, personality traits, relationships
- MAXIMUM compression is the goal - mark every duplicate you find
- **FORMAT IS NOT IMPORTANT** - It's OK if removing content breaks JSON structure or Markdown formatting
- **SEMANTIC UNIQUENESS ONLY** - The remaining content will be reprocessed later, so only keep unique information
- Don't worry about leaving valid JSON or complete sentences - just remove duplicates
- **STOP CONDITION**: If you have removed all duplicate content and there are no more duplicates to remove, DO NOT call the tool. Simply respond with a message indicating completion.

Be thorough and aggressive in identifying duplicates."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return messages, tools


__all__ = ["build_compress_content_payload"]
