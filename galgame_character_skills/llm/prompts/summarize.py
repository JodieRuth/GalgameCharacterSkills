"""summarize 相关 prompt 模块。"""

from typing import Any, Callable

from .shared import build_write_file_tool


def build_summarize_content_payload(
    content: str,
    role_name: str,
    instruction: str,
    output_file_path: str,
    output_language: str,
    vndb_data: dict[str, Any] | None,
    lang_names: dict[str, str],
    format_vndb_section: Callable[[dict[str, Any] | None, str], str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """构造文本归纳请求载荷。"""
    tools = build_write_file_tool("File content in markdown format")

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
        lang_name = lang_names.get(output_language, output_language)
        system_prompt += f"""

## OUTPUT LANGUAGE
You MUST write ALL content in {lang_name}.
- Character analysis: {lang_name}
- All descriptions and summaries: {lang_name}
ALL output must be in {lang_name}, regardless of the source text language."""

    if vndb_data:
        system_prompt += format_vndb_section(vndb_data, "## VNDB Character Information")

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Please analyze and summarize the following content, focusing exclusively on the character '{role_name}'. Save your summary to: {output_file_path}\n\nContent:\n{content}",
        },
    ]
    return messages, tools


def build_summarize_chara_card_payload(
    content: str,
    role_name: str,
    instruction: str,
    output_file_path: str,
    output_language: str,
    vndb_data: dict[str, Any] | None,
    lang_names: dict[str, str],
    format_vndb_section: Callable[[dict[str, Any] | None, str], str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """构造角色卡归纳请求载荷。"""
    tools = build_write_file_tool("File content in JSON format")

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
            "content": "当关键词被触发时插入的内容。使用对话格式：{{{{user}}}}: \\"问题\\"\\n{{{{char}}}}: \\"回答\\""
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
        system_prompt += format_vndb_section(vndb_data, "## VNDB Character Information")

    if output_language:
        lang_name = lang_names.get(output_language, output_language)
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
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Please analyze the following content and extract character analysis and lorebook entries for '{role_name}'.\n\nContent:\n{content}",
        },
    ]
    return messages, tools


__all__ = [
    "build_summarize_content_payload",
    "build_summarize_chara_card_payload",
]
