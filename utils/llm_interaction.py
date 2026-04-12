import litellm
import json
import sys
import os

litellm.enable_system_proxy = True

class LLMInteraction:
    _request_count = 0
    _total_requests = 0
    
    def __init__(self):
        self.baseurl = ""
        self.modelname = ""
        self.apikey = ""
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    def set_config(self, baseurl, modelname, apikey):
        self.baseurl = baseurl
        self.modelname = modelname
        self.apikey = apikey
        litellm.api_key = apikey
        if baseurl:
            litellm.api_base = baseurl
    
    @classmethod
    def set_total_requests(cls, total):
        cls._total_requests = total
        cls._request_count = 0
    
    def send_message(self, messages, tools=None, max_retries=3, use_counter=True):
        import time
        
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
            "tools": tools,
            "tool_choice": "auto"
        }
        
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
    
    def generate_cleanup_script(self, file_content, source_file_path, output_file_path):
        file_name = os.path.basename(source_file_path)
        name, ext = os.path.splitext(file_name)
        script_file_path = os.path.join(os.path.dirname(source_file_path), f"{name}_cleanup.py")
        
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
                                "description": "File content"
                            }
                        },
                        "required": ["file_path", "content"]
                    }
                }
            }
        ]
        
        system_prompt = f"""You are a professional text processing assistant.
Your task is to generate a Python cleanup and organization script based on the provided text format.

CRITICAL REQUIREMENTS:
1. Target Python version: {self.python_version}
2. Source file path: {source_file_path}
3. Output file path: {output_file_path}
4. Script file path (MUST save to this exact path): {script_file_path}
5. You MUST ONLY use Python's native text processing capabilities (str, re, os, sys, io, pathlib)
6. You are FORBIDDEN from using any external libraries (no pandas, no numpy, no third-party packages)
7. The script should read from the source file and write the cleaned content to the output file
8. Use only built-in Python modules for file I/O and text processing

The script should:
- Read the entire source file
- Clean and organize the content based on its format
- Handle encoding properly (UTF-8)
- Write the cleaned content to the specified output path
- Include error handling

IMPORTANT: Use the write_file tool to save the generated script to EXACTLY this path: {script_file_path}"""
        
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"Please generate a Python cleanup script based on the following text format (first 1000 lines):\n{file_content}"
            }
        ]
        
        return self.send_message(messages, tools), script_file_path
    
    def summarize_content(self, content, role_name, instruction, output_file_path):
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
        
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"Please analyze and summarize the following content, focusing EXCLUSIVELY on the character '{role_name}'. Save your summary to: {output_file_path}\n\nContent:\n{content}"
            }
        ]
        
        return self.send_message(messages, tools)
    
    def generate_skills_folder_init(self, summaries, role_name):
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
Your task is to create a complete skills folder structure based on the character summaries provided.

CHARACTER NAME: {role_name}

CONTENT GUIDELINES:
- Keep content APPROPRIATE and PROFESSIONAL
- Focus on personality, speech patterns, and thinking style
- AVOID excessive personal details, inappropriate content, or content that violates privacy
- Keep descriptions GENERAL and SUITABLE FOR PUBLIC USE
- DO NOT invent private or sensitive information not in the source material

FOLDER STRUCTURE:
Create ONE main version (folder name: {role_name}-skill-main/):

REQUIRED FILES:

1. SKILL.md - Main skill definition with frontmatter (CRITICAL - This is the entry point):
```markdown
---
name: {role_name}-perspective
description: |
  [Character]的思维框架与表达方式。
  用途：[一句话描述用途]
  激活方式：/{role_name}_chat [问题]
---

# [Character]

## 角色扮演规则

**此Skill激活后，直接以[Character]的身份回应。**

- 用「我」而非「[Character]会认为...」
- 直接用角色的语气、表达方式回答问题
- **⚠️ 第一优先级：必须使用用户的提问语言回答**
- 不跳出角色做meta分析（除非用户明确要求）

**语言规则（强制执行）**:
1. 检测用户提问的语言
2. 用完全相同的语言回答所有内容
3. 禁止混入其他语言（包括原文引用）
4. 如需引用原文，必须翻译为用户提问语言

**退出角色**：用户说「退出」「切回正常」「不用扮演了」时恢复正常模式

**默认激活方式**：`/{role_name}_chat [问题]`

---

## 核心原则

[描述角色的核心思维原则 - 基于文本中明确表现出的特点]

---

## 人格框架

[从提供的文本中提炼出角色的人格特征、行为模式、价值观等 - 保持适当和概括]

---

## 语言规则（最高优先级）

**⚠️ CRITICAL: 始终使用用户的提问语言进行回答。**

- **检测用户提问的语言，必须用相同语言回应**
- **禁止输出任何非用户提问语言的内容（包括原文引用）**
- **如果原文是其他语言，必须翻译为用户提问语言**
- **语言匹配优先于角色语气还原**

### 示例
- 用户用中文提问 → 必须用中文回答（所有内容，包括引用的台词）
- 用户用英文提问 → 必须用英文回答
- 用户用日文提问 → 必须用日文回答

---

## 表达方式

[用用户提问语言描述角色的语言风格特点]

### 语言风格特点
- [描述语气特点，如：活泼、直接、热情]
- [描述句式特点，如：多用感叹号、口语化]

### 标志性表达（用用户提问语言描述）
- [描述角色的典型表达方式，不要放原文]
- 例如：喜欢用充满活力的口号，而不是直接引用「この列車は...」

### 称呼习惯
- [描述角色如何称呼他人]

### 情绪表达方式
- [描述不同情绪下的语言特点]
```

2. soul.md - 角色的灵魂/核心定义（可选但推荐）：
```markdown
# Soul of {role_name}

## 核心驱动力
[角色行为背后的核心动机 - 基于文本证据]

## 价值观
[角色重视什么 - 基于文本中的言行]

## 行为模式
[角色如何与他人互动 - 基于文本中的表现]
```

3. limit.md - 限制和边界（会被移除生成-code版本）：
```markdown
# Limitations

## 内容限制
- 保持回答在适当范围内
- 不讨论过于私人的话题
- 基于提供的文本，不编造未提及的内容

## 禁止话题
- [根据角色特点设定]
```

4. 其他文件 - 放在 resource/ 文件夹下（可选）：
- 仅当有必要时创建额外文件
- 保持内容简洁和专业

IMPORTANT INSTRUCTIONS:
1. You can use the write_file tool MULTIPLE TIMES in a single response
2. Create SKILL.md (required), soul.md (recommended), limit.md (required)
3. Put any additional files in the resource/ folder
4. Use proper markdown formatting
5. Ensure file paths are correct: {role_name}-skill-main/filename.md or {role_name}-skill-main/resource/filename.md
6. Focus on SPEECH PATTERNS, THINKING STYLE, and GENERAL PERSONALITY TRAITS
7. KEEP CONTENT APPROPRIATE AND PROFESSIONAL - avoid excessive personal details
8. BASE ALL CONTENT on the provided summaries - do not invent private information
9. The SKILL.md should enable role-playing of the character's PUBLIC PERSONA

Use the write_file tool to create all necessary files. You may call it multiple times."""
        
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"Please generate a complete skills folder for character '{role_name}' based on the following summaries:\n{summaries}\n\nRemember to create ALL required files for BOTH versions (code and full). You can call the write_file tool multiple times. After creating all files, indicate completion."
            }
        ]
        
        return messages, tools
