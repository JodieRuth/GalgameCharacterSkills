# LLM 支撑层

## 1. 这一层负责什么

`llm/` 目录负责模型交互能力，而不是任务级业务流程。

当前主要包括：

- provider 配置归一化
- transport 与重试
- 请求级 runtime 统计
- `LLMInteraction`
- message flow 构造
- prompt 模板
- 角色卡字段与 prompt builder 辅助


## 2. 这一层不负责什么

`llm/` 不应长期承载：

- 完整任务 workflow
- checkpoint 恢复编排
- 输出目录落盘策略

这些内容应留在 application 层。


## 3. 当前设计特点

### 3.1 以能力模块组织

而不是以单个任务目录组织。

这意味着：

- provider 相关逻辑集中
- prompt 和 message flow 可以跨任务复用

### 3.2 通过 gateway 向上暴露

application 通常通过：

- `LLMGateway`

而不是直接在所有地方接触 `build_llm_client(...)`。


## 4. 目录内文档

建议继续阅读：

- `runtime.md`
- `transport.md`
- `prompts.md`
- `message-flows.md`
- `provider-config.md`
