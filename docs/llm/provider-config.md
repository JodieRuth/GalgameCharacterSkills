# Provider 配置

## 1. 核心文件

- `llm/provider_config.py`
- `llm/budget.py`


## 2. `provider_config.py`

这个模块负责：

- 根据 baseurl 规范化 provider/model 名称
- 构造 LiteLLM completion kwargs

它的作用是把 provider 差异收敛在一处，而不是散落在请求发送逻辑里。


## 3. `budget.py`

这个模块负责模型上下文窗口相关能力，例如：

- 查询模型上下文上限
- 压缩阈值辅助

它是配置查询接口和压缩策略的重要支撑。


## 4. 设计意义

provider 相关逻辑一旦分散到任务代码里，后续切换模型服务会非常痛苦。

当前把它收在 `llm/` 内部，是合理的。
