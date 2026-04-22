# LLM 运行时

## 1. 核心文件

- `llm/runtime.py`
- `llm/llm_interaction.py`
- `llm/factory.py`


## 2. `LLMRequestRuntime`

`LLMRequestRuntime` 用于记录单次任务中的 LLM 请求统计信息。

它负责：

- 跟踪总请求数
- 跟踪当前已发送次数
- 输出开始、成功、失败日志
- 输出响应预览

这让 long-running 任务在控制台中具备基本可观察性。


## 3. `LLMInteraction`

`LLMInteraction` 是当前模型交互的主客户端包装。

它负责：

- 保存 baseurl / model / apikey / retry 配置
- 构造 completion 参数
- 调用 transport
- 记录 runtime 日志
- 提取 tool calls


## 4. 运行时设计的意义

这套设计把“单次请求的交互逻辑”和“任务级业务流程”分开：

- request 级细节留在 `llm/`
- task 级编排留在 `application/`

这也是当前架构边界成立的重要前提之一。
