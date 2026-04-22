# LLM Transport

## 1. 核心文件

- `llm/transport.py`


## 2. 职责

`CompletionTransport` 负责：

- 调用 LiteLLM completion
- 执行重试
- 在每次尝试中触发回调


## 3. 为什么需要单独 transport

如果把重试和 provider 调用直接写进 `LLMInteraction`，客户端会很快变得更重。

单独 transport 的好处是：

- 请求发送策略集中
- 重试行为更容易调整
- 上层客户端逻辑更清晰


## 4. 当前实现特点

当前采用指数退避：

- 第一次失败后等待 `2^attempt` 秒

失败时不会抛出最终异常，而是：

- 调用失败回调
- 最终返回 `None`

这符合当前项目“业务层自己决定如何处理模型失败”的风格。
