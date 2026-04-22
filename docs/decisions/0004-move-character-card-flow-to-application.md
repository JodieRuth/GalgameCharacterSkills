# 0004 将角色卡流程迁移到 Application 层

## 背景

角色卡生成的 flow 和 tool loop 曾经放在 `llm/` 中，但它们实际上承担的是任务级 workflow，而不是纯模型能力。

## 决策

将角色卡的：

- flow
- tool loop

迁移到：

- `application/character_card/`

仅保留 prompt、字段模板和消息构造等纯 LLM 能力在 `llm/`。

## 影响

- `llm/` 职责更纯
- `application/character_card/` 边界更完整
- 避免出现 `llm -> application` 反向依赖
