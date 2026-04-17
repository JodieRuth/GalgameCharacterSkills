import litellm
import json
import sys
import os
from datetime import datetime

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
    _request_count = 0
    _total_requests = 0
    
    def __init__(self):
        self.baseurl = ""
        self.modelname = ""
        self.apikey = ""
        self.max_retries = 3
    
    def set_config(self, baseurl, modelname, apikey, max_retries=None):
        self.baseurl = baseurl
        self.modelname = modelname
        self.apikey = apikey
        if max_retries is not None and max_retries > 0:
            self.max_retries = max_retries
    
    @classmethod
    def set_total_requests(cls, total):
        cls._total_requests = total
        cls._request_count = 0
    
    def send_message(self, messages, tools=None, max_retries=None, use_counter=True):
        import time
        
        if max_retries is None:
            max_retries = self.max_retries
        model = self.modelname
        baseurl = self.baseurl.lower() if self.baseurl else ''
        
        if model and '/' not in model:
            if 'deepseek' in baseurl:
                model = f"deepseek/{model}"
            elif 'anthropic' in baseurl or 'claude' in baseurl:
                model = f"anthropic/{model}"
            elif 'gemini' in baseurl or 'google' in baseurl:
                model = f"google/{model}"
            else:
                model = f"openai/{model}"
        
        api_key_preview = self.apikey[:10] + "..." if self.apikey and len(self.apikey) > 10 else (self.apikey if self.apikey else "None")
        
        if use_counter and LLMInteraction._total_requests > 0:
            LLMInteraction._request_count += 1
            current = LLMInteraction._request_count
            total = LLMInteraction._total_requests
            remaining = total - current
            print(f"[LLM] Request {current}/{total} - Model: {model}, Base URL: {self.baseurl}")
        else:
            print(f"[LLM] Request - Model: {model}, Base URL: {self.baseurl}")
        
        print(f"[LLM] API Key: {api_key_preview}, Length: {len(self.apikey) if self.apikey else 0}")
        print(f"[LLM] Messages count: {len(messages)}, Tools: {'Yes' if tools else 'No'}")
        
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
        
        print(f"[LLM] Attempt 1/{max_retries}")
        
        for attempt in range(max_retries):
            try:
                response = litellm.completion(**kwargs)
                if use_counter and LLMInteraction._total_requests > 0:
                    current = LLMInteraction._request_count
                    total = LLMInteraction._total_requests
                    remaining = total - current
                    print(f"[LLM] Sent {current} requests, {remaining}/{total} remaining")
                else:
                    print(f"[LLM] Request completed")
                if response and hasattr(response, 'choices') and response.choices:
                    choice = response.choices[0]
                    if hasattr(choice, 'message'):
                        msg = choice.message
                        content_preview = msg.content[:100] + "..." if msg.content and len(msg.content) > 100 else msg.content
                        print(f"[LLM] Response content preview: {content_preview}")
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            print(f"[LLM] Tool calls: {len(msg.tool_calls)}")
                return response
            except Exception as e:
                print(f"[LLM] Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"[LLM] Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    if use_counter and LLMInteraction._total_requests > 0:
                        current = LLMInteraction._request_count
                        total = LLMInteraction._total_requests
                        remaining = total - current
                        print(f"[LLM] Sent {current} requests, {remaining}/{total} remaining - Failed")
                    else:
                        print(f"[LLM] Request failed")
                    return None
    
    def get_tool_response(self, response):
        if response and hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            if hasattr(choice, 'message') and hasattr(choice.message, 'tool_calls'):
                return choice.message.tool_calls
        return None
    
    def summarize_content(self, content, role_name, instruction, output_file_path, output_language="", vndb_data=None):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write file to local disk",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "File path"
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
        
        system_prompt = f"""You are a professional character analysis assistant.
Your task is to analyze text content and extract a comprehensive character profile for "{role_name}".

ANALYSIS APPROACH - Blend of third-person observation and first-person perspective:

## PART A: Character Memory (客观事实与经历)
Extract factual information about the character:
- Basic identity (name, age, appearance, background)
- Key life events and timeline
- Important relationships and their dynamics
- Core values and beliefs (as demonstrated through actions)
- Significant memories or turning points
- Habits and routines

Present this section as OBSERVED FACTS from the text, using third-person perspective.

## PART B: Character Persona (行为模式与表达风格)
Extract actionable behavioral patterns that can drive dialogue:

### Layer 1: Identity Anchors
- Who they are at their core
- Self-perception vs. how others see them
- Key identity markers

### Layer 2: Expression Style (CRITICAL - be specific)
- Speech patterns: exact phrases, sentence structures, verbal tics
- Tone variations by context (formal/casual/emotional)
- Punctuation and rhythm habits
- Vocabulary preferences (slang, technical terms, etc.)
- How they address different people

### Layer 3: Emotional & Decision Patterns
- How they express different emotions (joy, anger, sadness, anxiety)
- Decision-making style (impulsive/analytical/emotional)
- Conflict response patterns
- Stress coping mechanisms

### Layer 4: Behavioral Rules
- Physical habits and mannerisms
- Social interaction patterns
- Default responses to common situations
- "If-then" behavioral rules

## CRITICAL REQUIREMENTS:
1. Focus EXCLUSIVELY on "{role_name}" - ignore other characters except as they relate to {role_name}
2. For PART A: Use third-person descriptive tone ("She grew up in...", "He believes that...")
3. For PART B: Shift to actionable, almost instructional tone ("When happy, she tends to...", "Uses '~desu' endings when formal")
4. Include SPECIFIC examples from text - actual quotes, exact phrases, concrete scenarios
5. Distinguish between: (a) what's explicitly shown vs (b) what's reasonably inferred
6. Capture NUANCE: contradictions, growth, context-dependent behaviors

## OUTPUT FORMAT:
Use markdown with clear hierarchy:
- # for main title
- ## for Part A / Part B sections  
- ### for subsections
- #### for specific layers/categories
- Bullet points for lists
- Tables for comparative data (timeline, relationships)
- > blockquotes for direct text evidence

DO NOT:
- Invent details not supported by the text
- Over-generalize (avoid "she is energetic" without specific evidence)
- Confuse the character's voice with narrative description

Additional instructions: {instruction}"""

        if output_language:
            lang_name = LANG_NAMES.get(output_language, output_language)
            system_prompt += f"""

## OUTPUT LANGUAGE
You MUST write ALL content in {lang_name}.
- Character analysis: {lang_name}
- All descriptions and summaries: {lang_name}
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
                "content": f"Please analyze and summarize the following content, focusing exclusively on the character '{role_name}'. Save your summary to: {output_file_path}\n\nContent:\n{content}"
            }
        ]

        return self.send_message(messages, tools)
    
    def summarize_content_for_chara_card(self, content, role_name, instruction, output_file_path, output_language="", vndb_data=None):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write file to local disk",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "File path"
                            },
                            "content": {
                                "type": "string",
                                "description": "File content in JSON format"
                            }
                        },
                        "required": ["file_path", "content"]
                    }
                }
            }
        ]
        
        system_prompt = f"""You are a professional character analysis and lorebook extraction assistant.
Your task is to analyze text content and extract:
1. Character profile for "{role_name}"
2. Worldbook/Lorebook entries from the text

## OUTPUT FORMAT
You must use the write_file tool to save a JSON object with the following structure:

```json
{{
    "character_analysis": {{
        "name": "角色名称",
        "part_a_memory": {{
            "basic_identity": "基本身份信息：年龄、外貌特征（身高、体重、发色/瞳色、显著特征）",
            "key_life_events": ["重要人生事件1", "重要人生事件2", "转折点..."],
            "relationships": ["与家人/朋友/恋人/对手的关系动态..."],
            "core_values": "核心价值观和信念（通过行动展现的）",
            "significant_memories": "形成性格的关键记忆和经历",
            "habits_routines": "日常习惯、偏好、仪式"
        }},
        "part_b_persona": {{
            "identity_anchors": "核心身份认同、自我认知与他人认知的差异",
            "expression_style": {{
                "speech_patterns": "具体语言模式：常用句式、口癖、句尾词、标志性短语",
                "tone_variations": "不同情境下的语气变化（正式/随意/情感化）",
                "punctuation_rhythm": "说话节奏、停顿、强调方式",
                "vocabulary": "词汇偏好：俚语、专业术语、古语、口头禅",
                "address_patterns": "自称和对其他人的称呼方式"
            }},
            "emotional_patterns": {{
                "emotional_expression": "不同情绪的表达方式（喜悦/愤怒/悲伤/焦虑/恐惧）",
                "decision_style": "决策风格（冲动型/分析型/情感型/直觉型）",
                "conflict_response": "冲突应对模式（回避/对抗/妥协）",
                "stress_coping": "压力应对机制"
            }},
            "behavioral_rules": {{
                "physical_habits": "身体习惯和举止（手势、姿势、动作）",
                "social_patterns": "社交互动模式（主动/被动/观察者）",
                "default_responses": "常见情境的默认反应",
                "if_then_rules": "特定情境触发的行为规则"
            }}
        }},
        "appearance": "外貌描述，包含所有身体特征（整合自part_a）",
        "personality_traits": ["性格特点1", "性格特点2", ...],
        "speech_patterns": "语言风格总结（整合自part_b）",
        "background": "背景故事和经历（整合自part_a）",
        "relationships": ["关系1描述", "关系2描述", ...],
        "key_events": ["重要事件1", "重要事件2", ...],
        "behavior_patterns": "行为模式和习惯（整合自part_b）"
    }},
    "lorebook_entries": [
        {{
            "keys": ["关键词1", "关键词2", "别名"],
            "comment": "条目名称/注释",
            "content": "当关键词被触发时插入的内容。使用对话格式：{{{{user}}}}: \"问题\"\\n{{{{char}}}}: \"回答\""
        }}
    ]
}}
```

## CHARACTER ANALYSIS GUIDELINES

### PART A: Character Memory (客观事实与经历)
Extract factual information about the character:
- **Basic identity**: name, age, appearance (height, weight, hair/eye color, distinctive features)
- **Key life events**: timeline of important moments, turning points
- **Important relationships**: dynamics with family, friends, rivals, love interests
- **Core values and beliefs**: as demonstrated through actions and decisions
- **Significant memories**: formative experiences that shaped the character
- **Habits and routines**: daily patterns, preferences, rituals

Present this section as OBSERVED FACTS from the text, using third-person perspective.

### PART B: Character Persona (行为模式与表达风格)
Extract actionable behavioral patterns:

#### Layer 1: Identity Anchors
- Who they are at their core
- Self-perception vs. how others see them
- Key identity markers and self-image

#### Layer 2: Expression Style (CRITICAL - be specific)
- **Speech patterns**: exact phrases, sentence structures, verbal tics, sentence endings
- **Tone variations**: formal/casual/emotional contexts
- **Punctuation and rhythm**: speaking pace, pauses, emphasis
- **Vocabulary preferences**: slang, technical terms, archaic words, pet phrases
- **Address patterns**: how they refer to themselves and others

#### Layer 3: Emotional & Decision Patterns
- How they express different emotions (joy, anger, sadness, anxiety, fear)
- Decision-making style (impulsive/analytical/emotional/intuitive)
- Conflict response patterns (avoidance/confrontation/compromise)
- Stress coping mechanisms

#### Layer 4: Behavioral Rules
- Physical habits and mannerisms (gestures, postures, movements)
- Social interaction patterns (initiator/responder/observer)
- Default responses to common situations
- "If-then" behavioral rules

### IMPORTANT ANALYSIS PRINCIPLES
- Include SPECIFIC examples from text - actual quotes, exact phrases, concrete scenarios
- Distinguish between: (a) what's explicitly shown vs (b) what's reasonably inferred
- Capture NUANCE: contradictions, character growth, context-dependent behaviors
- Avoid over-generalization - provide evidence for each trait

## LOREBOOK ENTRIES GUIDELINES

### Entry Types to Extract:
- **Locations**: Places mentioned (cities, buildings, regions, landmarks)
- **Organizations**: Groups, factions, institutions, clubs, companies
- **Concepts**: Important ideas, systems, rules, cultural practices, beliefs
- **Items**: Significant objects with meaning (gifts, heirlooms, tools)
- **Events**: Historical or significant happenings, ceremonies, incidents
- **Other Characters**: Important people related to {role_name}

### Entry Quality Standards:
- Have 2-5 relevant keywords including aliases/variations
- Content should be from {role_name}'s perspective and voice
- Use dialogue format: {{{{user}}}} asks, {{{{char}}}} responds with authentic dialogue
- Include concrete details from the text, not generic descriptions
- Capture the emotional tone and relationship dynamics
- Each entry should reveal something about {role_name}'s worldview or experience

## LANGUAGE REQUIREMENT
You MUST write ALL content in the same language as the source text.
- If the source text is in Japanese, write the analysis and lorebook entries in Japanese
- If the source text is in Chinese, write in Chinese
- If the source text is in English, write in English
- Character dialogue should match the original text's language
- This ensures the character card maintains the authentic voice of the source material

## CRITICAL REQUIREMENTS
1. Use the write_file tool to save the JSON to: {output_file_path}
2. Return ONLY valid JSON in the file content
3. Be thorough - extract ALL relevant lorebook entries you can find
4. Focus on information that helps understand {role_name}'s world
5. Do not invent details not supported by the text

Additional instructions: {instruction}"""

        if vndb_data:
            vndb_section = _format_vndb_section(vndb_data, "## VNDB Character Information")
            system_prompt += vndb_section

        if output_language:
            lang_name = LANG_NAMES.get(output_language, output_language)
            system_prompt += f"""

## OUTPUT LANGUAGE OVERRIDE
The user has requested output in {lang_name}.
IGNORE the source text language - write ALL content in {lang_name}.
- Character analysis: {lang_name}
- Lorebook entries (keys, comments, content): {lang_name}
- Dialogue in lorebook content: {lang_name}
ALL output must be in {lang_name}, regardless of the source text language.

## IMPORTANT: DO NOT TRANSLATE GAME/WORK TITLES
Game titles and work titles MUST be kept in their ORIGINAL form.
For example: "見上げてごらん、夜空の星を" should remain "見上げてごらん、夜空の星を" (NOT translated).
Character names, location names, and other proper nouns can be translated or kept as-is."""

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"Please analyze the following content and extract character analysis and lorebook entries for '{role_name}'.\n\nContent:\n{content}"
            }
        ]

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
        from .tool_handler import ToolHandler
        
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
        
        merged_entries = ToolHandler.merge_lorebook_entries(all_lorebook_entries)
        lorebook_entries = ToolHandler.build_lorebook_entries(merged_entries, start_id=0)
        
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
        
        language_instruction = ""
        if output_language:
            lang_name = LANG_NAMES.get(output_language, output_language)
            language_instruction = f"""

## LANGUAGE REQUIREMENT (CRITICAL - HIGHEST PRIORITY)
You MUST write the ENTIRE character card in {lang_name}.
ALL content including fields, world book entries, example messages, and dialogue MUST be in {lang_name}.
- Character name, description, personality: {lang_name}
- First message and example messages: {lang_name}
- System prompt and all instructions: {lang_name}
- World book entries (keys, comments, content): {lang_name}

## IMPORTANT: DO NOT TRANSLATE GAME/WORK TITLES
Game titles and work titles MUST be kept in their ORIGINAL form.
For example:
- "見上げてごらん、夜空の星を" should remain "見上げてごらん、夜空の星を" (NOT translated to "A Sky Full of Stars" or any other title)
- "A Sky Full of Stars" should remain "A Sky Full of Stars" (NOT translated)

Character names, location names, and other proper nouns can be translated or kept as-is based on common usage.
- Character dialogue in mes_example: {lang_name}
Do NOT use Japanese, English, or any other language. ALL text must be in {lang_name}."""

        system_prompt = f"""You are a professional SillyTavern character card generator.

ROLE: {role_name}

CHARACTER DATA:
{json.dumps(integrated_analysis, ensure_ascii=False, indent=2)}{vndb_ref}

## DATA PRIORITY (HIGHEST TO LOWEST)
1. **VNDB Data** - Use as authoritative source for character appearance, physical stats (height, weight, age, etc.), and basic information
2. **Latest Timeline** - When analyzing story data, prioritize the most recent events and character development as the current canon
3. **Story Analysis** - Use for personality details, relationships, and narrative context
4. **Earlier Events** - Use for backstory and character history only

YOUR TASK:
Generate a complete SillyTavern v3 character card by calling the write_field tool multiple times.{language_instruction}

AVAILABLE FIELDS:
1. **name** - Character name (string)
2. **description** - Main description with personality traits, appearance, etc. (string with SillyTavern format)
3. **personality** - Short personality summary (string)
4. **first_mes** - First message/greeting (string)
5. **mes_example** - Example conversation messages (string with <START> separators)
6. **scenario** - Setting/context (string)
7. **system_prompt** - Main AI instructions (string)
8. **post_history_instructions** - Context reinforcement (string)
9. **depth_prompt** - Deep psychology layer (string)

NOTE: Do NOT write creatorcomment, creator_notes, or world_name fields. These will be auto-generated by the system.

## SILLYTAVERN FORMAT GUIDELINES

**Description Field Format:**
```
[{{char}}'s Personality= "trait1", "trait2", "trait3", ...]
[{{char}}'s body= "feature1", "feature2", ...]
[{{char}}'s outfit= "clothing1", "clothing2", ...]
[{{char}} likes= "like1", "like2", ...]
[{{char}} dislikes= "dislike1", "dislike2", ...]
```

**Example Messages Format:**
```
<START>
{{user}}: "Hello there!"
{{char}}: "Oh! *jumps slightly* I didn't see you there..."
<START>
{{user}}: "How are you?"
{{char}}: "*smiles shyly* I'm doing well, thank you for asking..."
```

**System Prompt Best Practices:**
- Use {{user}} and {{char}} placeholders
- Define speech patterns clearly
- Include physical mannerisms
- Set personality boundaries

Call write_field for each field. Set is_complete=true on the last call."""

        if is_resuming:
            messages = ckpt_messages
            tool_call_count = ckpt_iteration_count or 0
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate the complete character card for '{role_name}'. Use the write_field tool to write each field. Start with the most important fields (name, description, system_prompt, first_mes)."}
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
                    parsed = ToolHandler.parse_llm_json_response(content)
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
        
        result = ToolHandler.fill_json_template(template_path, output_path, field_mappings)
        
        return {
            'success': True,
            'output_path': output_path,
            'fields_written': [k for k, v in fields_data.items() if v and k != 'character_book_entries'],
            'result': result
        }
    
    def _integrate_analyses(self, role_name, all_analyses, vndb_data=None):
        vndb_section = _format_vndb_section(vndb_data, "## VNDB Character Information", bullet="")
        
        system_prompt = f"""You are a data integration assistant for SillyTavern character card generation.

ROLE: {role_name}

Your task is to merge multiple character analyses into a single comprehensive profile that will be used to generate a SillyTavern v3 character card.{vndb_section}

## OUTPUT FORMAT
Return a JSON object with this structure:
```json
{{
    "name": "角色完整名称",
    "appearance": "详细外貌描述，包括：头发、眼睛、身材、服装等",
    "personality_traits": ["性格特点1", "性格特点2", ...],
    "speech_patterns": "语言风格、口癖、常用句式、语气特点",
    "background": "背景故事和经历",
    "relationships": ["与重要人物的关系描述"],
    "key_events": ["重要事件1", "事件2"],
    "behavior_patterns": "行为模式、习惯、典型反应",
    "world_name": "世界观/世界名称",
    "key_concepts": ["世界观中的重要概念"],
    "example_dialogues": ["示例对话片段1", "片段2"],
    "characteristic_actions": ["典型动作1", "动作2"]
}}
```

## CRITICAL REQUIREMENTS FOR SILLYTAVERN FORMAT
1. **Appearance**: Be extremely detailed - hair color/style, eye color, skin, clothing, distinctive features
2. **Personality Traits**: List 20-30 specific adjectives (caring, protective, shy, energetic, etc.)
3. **Speech Patterns**: Include specific verbal tics, sentence structures, honorifics, slang
4. **Characteristic Actions**: Physical mannerisms (fidgeting, smiling, hair-twirling, etc.)
5. **Example Dialogues**: Include actual dialogue examples showing how they speak
6. **World Context**: Setting, time period, important world elements

## RULES
- Return ONLY valid JSON
- Be comprehensive and specific
- Preserve ALL unique details from each analysis
- If VNDB data is provided, use it as authoritative source for appearance and basic character info
- If information conflicts, include both variations
- Prioritize concrete examples over generalizations"""
        
        analyses_json = json.dumps(all_analyses, ensure_ascii=False, indent=2)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please integrate these character analyses for '{role_name}':\n\n{analyses_json}\n\nIf the output would be too long, you can output multiple responses. Each response should be a complete valid JSON. Indicate if you need to continue."}
        ]
        
        response = self.send_message(messages, use_counter=False)
        
        if response and response.choices:
            content = response.choices[0].message.content
            from .tool_handler import ToolHandler
            result = ToolHandler.parse_llm_json_response(content) or {}
            return result
        return {}
