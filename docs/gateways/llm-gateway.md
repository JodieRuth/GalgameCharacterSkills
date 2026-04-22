# LLMGateway

## 1. 入口文件

- `galgame_character_skills/gateways/llm_gateway.py`


## 2. 职责

`LLMGateway` 负责向 application 层暴露两类能力：

- 创建 LLM 客户端
- 创建请求级运行时


## 3. 为什么不是直接在 application 里构造 LLMInteraction

如果 application 直接知道：

- 如何 build client
- 如何初始化 runtime

那么：

- provider 相关细节会泄漏到业务流程
- 测试替换会变麻烦

通过 gateway 收口后，application 只表达：

- 我需要一个客户端
- 我需要一个请求运行时


## 4. 默认实现

当前默认实现会：

- 调用 `build_llm_client(...)`
- 调用 `LLMInteraction.build_runtime(...)`

这意味着 provider 与 transport 层仍然留在 `llm/` 目录，而不是扩散到 application。
