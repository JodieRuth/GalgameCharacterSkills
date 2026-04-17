import json
import sys
import os
from datetime import datetime
from ..gateways.tool_gateway import DefaultToolGateway
from .transport import CompletionTransport
from .runtime import LLMRequestRuntime
from .prompts import (
    build_summarize_content_payload,
    build_summarize_chara_card_payload,
)
from ..utils.prompt_builders import (
    build_character_card_language_instruction,
    build_character_card_system_prompt,
    build_character_card_user_prompt,
    build_integrate_analyses_system_prompt,
    build_integrate_analyses_user_prompt,
)

LANG_NAMES = {"zh": "中文", "en": "English", "ja": "日本語"}

def _format_vndb_section(vndb_data, title, bullet="-"):
    if not vndb_data:
        return ""

    entries = []
    field_map = [
        ("name", "Name"),
        ("original_name", "Original Name"),
        ("aliases", "Aliases"),
        ("description", "Description"),
        ("age", "Age"),
        ("birthday", "Birthday"),
        ("blood_type", "Blood Type"),
        ("height", "Height"),
        ("weight", "Weight"),
        ("traits", "Traits"),
        ("vns", "Visual Novels"),
    ]

    for key, label in field_map:
        value = vndb_data.get(key)
        if not value:
            continue
        if key == "aliases" and isinstance(value, list):
            value = ", ".join(value)
        elif key == "traits" and isinstance(value, list):
            value = ", ".join(value)
        elif key == "vns" and isinstance(value, list):
            value = ", ".join(value[:3])
        elif key == "height":
            value = f"{value}cm"
        elif key == "weight":
            value = f"{value}kg"
        prefix = f"{bullet} " if bullet else ""
        entries.append(f"{prefix}{label}: {value}")

    if vndb_data.get('bust') and vndb_data.get('waist') and vndb_data.get('hips'):
        prefix = f"{bullet} " if bullet else ""
        entries.append(f"{prefix}Measurements: {vndb_data['bust']}-{vndb_data['waist']}-{vndb_data['hips']}cm")

    if not entries:
        return ""

    return f"\n\n{title}\n" + "\n".join(entries) + "\n"

class LLMInteraction:
    def __init__(self):
        self.baseurl = ""
        self.modelname = ""
        self.apikey = ""
        self.max_retries = 3
        self.tool_gateway = DefaultToolGateway()
        self.transport = CompletionTransport()
    
    def set_config(self, baseurl, modelname, apikey, max_retries=None):
        self.baseurl = baseurl
        self.modelname = modelname
        self.apikey = apikey
        if max_retries is not None and max_retries > 0:
            self.max_retries = max_retries
    
    @classmethod
    def set_total_requests(cls, total):
        LLMRequestRuntime.set_total_requests(total)

    def _normalize_model_name(self):
        model = self.modelname
        baseurl = self.baseurl.lower() if self.baseurl else ''

        if model and '/' not in model:
            if 'deepseek' in baseurl:
                return f"deepseek/{model}"
            if 'anthropic' in baseurl or 'claude' in baseurl:
                return f"anthropic/{model}"
            if 'gemini' in baseurl or 'google' in baseurl:
                return f"google/{model}"
            return f"openai/{model}"
        return model

    def _build_completion_kwargs(self, model, messages, tools):
        kwargs = {
            "model": model,
            "messages": messages,
            "timeout": 300
        }

        if 'google' in model or 'gemini' in model:
            kwargs["safety_settings"] = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if self.apikey:
            kwargs["api_key"] = self.apikey
        if self.baseurl:
            kwargs["api_base"] = self.baseurl
        return kwargs

    def _log_request_start(self, model, messages, tools, use_counter):
        LLMRequestRuntime.log_request_start(
            model=model,
            baseurl=self.baseurl,
            apikey=self.apikey,
            messages=messages,
            tools=tools,
            use_counter=use_counter,
        )

    def _log_request_success(self, use_counter):
        LLMRequestRuntime.log_request_success(use_counter=use_counter)

    def _log_response_preview(self, response):
        LLMRequestRuntime.log_response_preview(response)

    def _log_request_failed(self, use_counter):
        LLMRequestRuntime.log_request_failed(use_counter=use_counter)
    
    def send_message(self, messages, tools=None, max_retries=None, use_counter=True):
        if max_retries is None:
            max_retries = self.max_retries
        model = self._normalize_model_name()
        self._log_request_start(model=model, messages=messages, tools=tools, use_counter=use_counter)
        kwargs = self._build_completion_kwargs(model=model, messages=messages, tools=tools)
        
        print(f"[LLM] Attempt 1/{max_retries}")

        def _on_attempt_failed(attempt, error, retries):
            print(f"[LLM] Attempt {attempt + 1} failed: {error}")

        def _on_retry_wait(wait_time, attempt, retries):
            print(f"[LLM] Retrying in {wait_time} seconds...")

        def _on_success(response):
            self._log_request_success(use_counter=use_counter)
            self._log_response_preview(response)

        def _on_final_failure(error):
            self._log_request_failed(use_counter=use_counter)

        return self.transport.complete_with_retry(
            kwargs=kwargs,
            max_retries=max_retries,
            on_attempt_failed=_on_attempt_failed,
            on_retry_wait=_on_retry_wait,
            on_success=_on_success,
            on_final_failure=_on_final_failure,
        )
    
    def get_tool_response(self, response):
        if response and hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            if hasattr(choice, 'message') and hasattr(choice.message, 'tool_calls'):
                return choice.message.tool_calls
        return None
    
    def summarize_content(self, content, role_name, instruction, output_file_path, output_language="", vndb_data=None):
        messages, tools = build_summarize_content_payload(
            content=content,
            role_name=role_name,
            instruction=instruction,
            output_file_path=output_file_path,
            output_language=output_language,
            vndb_data=vndb_data,
            lang_names=LANG_NAMES,
            format_vndb_section=_format_vndb_section,
        )
        return self.send_message(messages, tools)
    
    def summarize_content_for_chara_card(self, content, role_name, instruction, output_file_path, output_language="", vndb_data=None):
        messages, tools = build_summarize_chara_card_payload(
            content=content,
            role_name=role_name,
            instruction=instruction,
            output_file_path=output_file_path,
            output_language=output_language,
            vndb_data=vndb_data,
            lang_names=LANG_NAMES,
            format_vndb_section=_format_vndb_section,
        )
        return self.send_message(messages, tools)
    
    def generate_skills_folder_init(self, summaries, role_name, output_language="", vndb_data=None):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write file to local disk. You can call this tool multiple times to create multiple files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "File path including folder structure"
                            },
                            "content": {
                                "type": "string",
                                "description": "File content in markdown format"
                            }
                        },
                        "required": ["file_path", "content"]
                    }
                }
            }
        ]
        
        system_prompt = f"""You are a professional skills folder generator.
Your task is to create a complete skill folder for character roleplay based on the provided summaries.

CHARACTER NAME: {role_name}

Follow these skill design principles:
- Keep SKILL.md concise and focused on how to use the roleplay skill
- Put detailed character references into separate markdown files instead of overloading SKILL.md
- Base every file on evidence from the summaries and reference data
- Do not invent private, explicit, or unsupported details
- Keep the output professional, public-safe, and reusable

FOLDER STRUCTURE:
Create exactly ONE folder: {role_name}-skill-main/

REQUIRED FILES:

1. SKILL.md
- This is the entry point of the skill
- It must contain ONLY YAML frontmatter with `name` and `description`
- The description must clearly state what the skill does and when to use it
- The body should be procedural and concise, telling the model to roleplay as the character directly
- The body should explicitly reference the detailed files in `resource/` and explain what each file is for
- Do not duplicate long reference material inside SKILL.md

Expected structure:
```markdown
---
name: {role_name}-perspective
description: |
  [Character]的思维框架与表达方式。
  用途：以[Character]的身份进行对话。
  激活方式：/{role_name}_chat [问题]
---

# [Character]

## Roleplay Rules

**When this skill is activated, respond directly as [Character].**

- Use "I" instead of "[Character] would think..."
- Answer questions directly in the character's tone and expression style
- **⚠️ TOP PRIORITY: Must use the same language as the user's question**
- Do not break character for meta-analysis (unless explicitly requested)

**Language Rules (Strictly Enforced)**:
1. Detect the language of the user's question
2. Respond entirely in that same language
3. Do not mix in other languages (including original text quotes)
4. If quoting original text, it must be translated to the user's language

**Exit Roleplay**: Return to normal mode when user says "exit", "switch back", "stop roleplaying", etc.

**Default Activation**: `/{role_name}_chat [question]`

---

## Core Principles

[Describe the character's core thinking principles based on evidence from the text]

---

## Personality Framework

[Extract the character's personality traits, behavior patterns, and values from the provided text - keep appropriate and general]

---

## Language Rules (Highest Priority)

**⚠️ CRITICAL: Always respond in the same language as the user's question.**

- **Detect the user's question language and respond in that language**
- **Do not output any content in non-user languages (including original quotes)**
- **If original text is in another language, translate it to the user's question language**
- **Language matching takes priority over character tone authenticity**

### Examples
- User asks in Chinese → Must respond in Chinese (all content, including quoted lines)
- User asks in English → Must respond in English
- User asks in Japanese → Must respond in Japanese

---

## Expression Style

[Describe the character's language style in the user's question language]

### Speech Pattern Characteristics
- [Describe tone traits, e.g.: lively, direct, enthusiastic]
- [Describe sentence patterns, e.g.: frequent exclamation marks, colloquial]

### Signature Expressions (describe in user's language)
- [Describe the character's typical expressions without using original text]
- Example: Likes to use energetic slogans instead of directly quoting "This train is..."

### Addressing Habits
- [Describe how the character addresses others]

### Emotional Expression
- [Describe language characteristics in different emotional states]

---

## Resource Map
- Read `soul.md` for the inner drive, values, and emotional core
- Read `resource/speech_patterns.md` for verbal style and phrasing habits
- Read `resource/behavior_guide.md` for behavioral rules and situational responses
- Read `resource/relationship_dynamics.md` for important relationship dynamics with other characters
- Read `resource/key_life_events.md` for major experiences, turning points, and memory anchors
- Read `limit.md` for boundaries and unsupported areas

## Usage Notes
- Prioritize consistent voice, worldview, and behavior over plot recitation
- When facts are uncertain, stay within the strongest evidence from the summaries
```

2. soul.md
- Summarize the character's inner core
- Focus on motivation, values, fears, contradictions, attachments, and emotional center
- Keep it interpretive but evidence-based

Suggested sections:
```markdown
# Soul of {role_name}

## Core Drive
## Values and Beliefs
## Emotional Core
## Inner Contradictions
## Growth Arc
```

3. limit.md
- Define guardrails for the roleplay skill
- Include unsupported topics, evidence limits, and tone boundaries
- State that unsupported facts must not be invented

Suggested sections:
```markdown
# Limitations

## Scope Boundaries
## Evidence Rules
## Topic Restrictions
## Roleplay Exit Conditions
```

4. resource/behavior_guide.md
- Required
- Describe repeatable behavior rules, habits, reactions, and situational defaults

5. resource/speech_patterns.md
- Required
- Describe speech rhythm, wording, sentence habits, address patterns, tone shifts, and sample expression patterns

6. resource/relationship_dynamics.md
- Required
- New reference file dedicated to important relationships with other characters
- Include relationship type, emotional dynamic, behavior around that person, trust/conflict pattern, and why the relationship matters
- Prefer structured sections per character or per relationship cluster

7. resource/key_life_events.md
- Required
- New reference file dedicated to important life experiences and turning points
- Include formative events, emotional impact, later behavioral influence, and what memories remain central to the persona
- Organize chronologically when possible

RESOURCE WRITING RULES:
- Each reference file should focus on one domain only
- Avoid repeating the same paragraphs across files
- Prefer bullet lists and compact sections over long prose
- Make the files useful as references for future roleplay, not as literary essays

IMPORTANT INSTRUCTIONS:
1. Use the write_file tool multiple times if needed
2. Create all seven required files:
   - {role_name}-skill-main/SKILL.md
   - {role_name}-skill-main/soul.md
   - {role_name}-skill-main/limit.md
   - {role_name}-skill-main/resource/behavior_guide.md
   - {role_name}-skill-main/resource/speech_patterns.md
   - {role_name}-skill-main/resource/relationship_dynamics.md
   - {role_name}-skill-main/resource/key_life_events.md
3. Use valid markdown in every file
4. Keep SKILL.md lean; move detail into resource files
5. Focus on PUBLIC PERSONA, THINKING STYLE, SPEECH PATTERNS, RELATIONSHIPS, and IMPORTANT EXPERIENCES
6. Base all content on the summaries and reference data only
7. Do not create alternative versions or extra folders unless explicitly necessary

OPTIONAL ADDITIONAL FILES:
After creating the seven required files, you MAY create additional files in the resource/ folder if you believe they would enhance the roleplay experience. For example:
- Additional character relationship files
- Setting/world-building details
- Specific scenario guides
- Character development notes
- Any other supplementary material that would be valuable

Use the write_file tool to create all required files."""

        if output_language:
            lang_name = LANG_NAMES.get(output_language, output_language)
            system_prompt += f"""

## OUTPUT LANGUAGE REQUIREMENT
You MUST write ALL content in {lang_name}.
- SKILL.md, soul.md, limit.md, and all resource markdown files: ALL in {lang_name}
- Character descriptions: {lang_name}
- All instructions and content: {lang_name}
ALL output must be in {lang_name}, regardless of the source text language."""

        if vndb_data:
            vndb_section = _format_vndb_section(vndb_data, "## VNDB Character Information")
            system_prompt += vndb_section

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"Please generate a complete skill folder for character '{role_name}' based on the following compacted summaries:\n{summaries}\n\nCreate the single required folder structure exactly as specified. In SKILL.md, explicitly define the dependency and reading relationship between SKILL.md and the other markdown resources, including which file owns which type of information. You can call the write_file tool multiple times. After creating all required files, indicate completion."
            }
        ]
        
        return messages, tools

    def compress_content_with_llm(self, group_files_content, group_info):
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
                                            "description": "The filename where the duplicate content is located (e.g., 'summary_001.md')"
                                        },
                                        "content": {
                                            "type": "string",
                                            "description": "The exact duplicate content section to be removed. Must match the content in the file exactly."
                                        }
                                    },
                                    "required": ["filename", "content"]
                                },
                                "description": "List of duplicate sections to remove, each containing filename and the exact content to remove"
                            }
                        },
                        "required": ["file_sections"]
                    }
                }
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
            {"role": "user", "content": user_prompt}
        ]
        
        return messages, tools

    def generate_character_card_with_tools(self, role_name, all_analyses, all_lorebook_entries, output_path, creator="", vndb_data=None, output_language="", checkpoint_id=None, ckpt_messages=None, ckpt_fields_data=None, ckpt_iteration_count=None):
        integrated_analysis = self._integrate_analyses(role_name, all_analyses, vndb_data)
        
        vndb_ref = _format_vndb_section(vndb_data, "VNDB REFERENCE DATA (HIGHEST PRIORITY - Use these values as authoritative source for character appearance and basic info)", bullet="")
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "write_field",
                    "description": "Write a specific field to the character card JSON file. Call this tool multiple times to write different fields.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "field_name": {
                                "type": "string",
                                "description": "The name of the field to write. Must be one of: name, description, personality, first_mes, mes_example, scenario, system_prompt, post_history_instructions, depth_prompt",
                                "enum": ["name", "description", "personality", "first_mes", "mes_example", "scenario",
                                        "system_prompt", "post_history_instructions", "depth_prompt"]
                            },
                            "content": {
                                "type": "string",
                                "description": "The content to write for this field. For string fields, provide the text. For list fields (like personality traits), provide a JSON array string."
                            },
                            "is_complete": {
                                "type": "boolean",
                                "description": "Set to true if this is the last field you want to write. The system will finalize the character card after this."
                            }
                        },
                        "required": ["field_name", "content"]
                    }
                }
            }
        ]
        
        merged_entries = self.tool_gateway.merge_lorebook_entries(all_lorebook_entries)
        lorebook_entries = self.tool_gateway.build_lorebook_entries(merged_entries, start_id=0)
        
        base_name = role_name
        if vndb_data and vndb_data.get('name'):
            base_name = vndb_data['name']
        
        fields_data = {
            "name": base_name,
            "description": "",
            "personality": "",
            "first_mes": "",
            "mes_example": "",
            "scenario": "",
            "system_prompt": "",
            "post_history_instructions": "",
            "depth_prompt": "",
            "creatorcomment": f"Character card for {base_name}" + (f" (VNDB: {vndb_data.get('vndb_id', '')})" if vndb_data else ""),
            "world_name": base_name,
            "create_date": datetime.now().isoformat(),
            "creator": creator or "AI Character Generator",
            "tags": ["character", base_name.lower().replace(" ", "_")],
            "character_book_entries": lorebook_entries
        }

        is_resuming = ckpt_messages is not None and len(ckpt_messages) > 0
        if is_resuming and ckpt_fields_data:
            for key in fields_data:
                if key in ckpt_fields_data and ckpt_fields_data[key]:
                    if key == "character_book_entries":
                        continue
                    fields_data[key] = ckpt_fields_data[key]
        
        language_instruction = build_character_card_language_instruction(output_language, LANG_NAMES)
        integrated_analysis_json = json.dumps(integrated_analysis, ensure_ascii=False, indent=2)
        system_prompt = build_character_card_system_prompt(
            role_name=role_name,
            integrated_analysis_json=integrated_analysis_json,
            vndb_ref=vndb_ref,
            language_instruction=language_instruction,
        )

        if is_resuming:
            messages = ckpt_messages
            tool_call_count = ckpt_iteration_count or 0
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": build_character_card_user_prompt(role_name)}
            ]
            tool_call_count = 0
        
        max_tool_calls = 50 
        
        while tool_call_count < max_tool_calls:
            if checkpoint_id:
                from .checkpoint_manager import CheckpointManager
                mgr = CheckpointManager()
                mgr.save_llm_state(
                    checkpoint_id, messages=messages,
                    iteration_count=tool_call_count,
                    fields_data={k: v for k, v in fields_data.items() if k != 'character_book_entries'}
                )

            response = self.send_message(messages, tools=tools, use_counter=False)
            
            if not response or not response.choices:
                if checkpoint_id:
                    from .checkpoint_manager import CheckpointManager
                    mgr = CheckpointManager()
                    mgr.save_llm_state(
                        checkpoint_id, messages=messages,
                        last_response=None, iteration_count=tool_call_count,
                        fields_data={k: v for k, v in fields_data.items() if k != 'character_book_entries'}
                    )
                return {
                    'success': False,
                    'message': 'LLM交互失败',
                    'can_resume': True
                }
            
            message = response.choices[0].message
            
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "write_field":
                        try:
                            args = json.loads(tool_call.function.arguments)
                            field_name = args.get("field_name")
                            content = args.get("content")
                            is_complete = args.get("is_complete", False)
                            
                            if field_name in ["creatorcomment", "creator_notes", "world_name"]:
                                pass
                            elif field_name and field_name in fields_data:
                                fields_data[field_name] = content
                                if is_complete:
                                    tool_call_count = max_tool_calls  
                        except Exception:
                            pass
                
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                        } for tc in message.tool_calls
                    ]
                })
                
                for tool_call in message.tool_calls:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"status": "success", "message": f"Field written successfully"})
                    })
                
                tool_call_count += 1
            else:
                content = message.content
                
                try:
                    parsed = self.tool_gateway.parse_llm_json_response(content)
                    if parsed:
                        for key in fields_data.keys():
                            if key in parsed and key != "character_book_entries":
                                fields_data[key] = parsed[key]
                except Exception:
                    pass
                
                break

            if checkpoint_id:
                from .checkpoint_manager import CheckpointManager
                mgr = CheckpointManager()
                mgr.save_llm_state(
                    checkpoint_id, messages=messages,
                    last_response=response, iteration_count=tool_call_count,
                    fields_data={k: v for k, v in fields_data.items() if k != 'character_book_entries'}
                )
        
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'utils', 'chara_card_template.json')
        
        field_mappings = {
            "{{name}}": fields_data["name"],
            "{{description}}": fields_data["description"],
            "{{personality}}": fields_data["personality"],
            "{{first_mes}}": fields_data["first_mes"],
            "{{mes_example}}": fields_data["mes_example"],
            "{{scenario}}": fields_data["scenario"],
            "{{create_date}}": fields_data["create_date"],
            "{{creatorcomment}}": fields_data["creatorcomment"],
            "{{system_prompt}}": fields_data["system_prompt"],
            "{{post_history_instructions}}": fields_data["post_history_instructions"],
            "{{tags}}": fields_data["tags"],
            "{{creator}}": fields_data["creator"],
            "{{world_name}}": fields_data["world_name"],
            "{{depth_prompt}}": fields_data["depth_prompt"],
            "{{character_book_entries}}": fields_data["character_book_entries"],
        }
        
        result = self.tool_gateway.fill_json_template(template_path, output_path, field_mappings)
        
        return {
            'success': True,
            'output_path': output_path,
            'fields_written': [k for k, v in fields_data.items() if v and k != 'character_book_entries'],
            'result': result
        }
    
    def _integrate_analyses(self, role_name, all_analyses, vndb_data=None):
        vndb_section = _format_vndb_section(vndb_data, "## VNDB Character Information", bullet="")
        system_prompt = build_integrate_analyses_system_prompt(role_name, vndb_section)
        
        analyses_json = json.dumps(all_analyses, ensure_ascii=False, indent=2)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_integrate_analyses_user_prompt(role_name, analyses_json)}
        ]
        
        response = self.send_message(messages, use_counter=False)
        
        if response and response.choices:
            content = response.choices[0].message.content
            result = self.tool_gateway.parse_llm_json_response(content) or {}
            return result
        return {}
