# ToolGateway

## 1. 入口文件

- `galgame_character_skills/gateways/tool_gateway.py`


## 2. 职责

`ToolGateway` 负责暴露和工具调用相关的能力：

- 执行 tool call
- 解析 LLM 返回的 JSON
- 合并 lorebook entries
- 构造 lorebook entries
- 填充角色卡 JSON 模板


## 3. 为什么它不是单一职责的纯 executor

因为在当前系统里，“工具能力”并不只是执行文件写入之类动作，还包括一部分：

- 与角色卡 / lorebook 生成有关的结构处理

从设计纯度上看它偏宽，但从当前项目体量看仍然可控。


## 4. 默认实现

默认实现直接委托给：

- `ToolHandler`

这意味着 gateway 在这里主要扮演“边界隔离器”，而不承担复杂逻辑。
