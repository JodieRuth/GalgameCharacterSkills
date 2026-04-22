# Prompt 组织

## 1. 核心目录

- `llm/prompts/`
- `llm/card_prompt_builders.py`
- `llm/character_card_fields.py`


## 2. 当前 prompt 组织方式

当前 prompt 组织分成两类：

### 2.1 通用 prompt 模块

位于：

- `llm/prompts/summarize.py`
- `llm/prompts/skills.py`
- `llm/prompts/character_card.py`
- `llm/prompts/shared.py`

### 2.2 角色卡专用 builder

位于：

- `card_prompt_builders.py`
- `character_card_fields.py`


## 3. 为什么要这样拆

因为项目里的 prompt 既有“任务主 prompt”，也有“字段级、模板级辅助 prompt”。

统一塞进一个文件会很快失控，因此当前拆分方式是合理的。


## 4. 与 application 的关系

application 层不直接拼接 prompt 文本，而是通过 message flow 或 builder 间接使用这些 prompt。

这样做可以减少：

- 任务流程代码里的长字符串
- prompt 变动对业务编排可读性的破坏
