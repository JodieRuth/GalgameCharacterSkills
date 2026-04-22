# ExecutorGateway

## 1. 入口文件

- `galgame_character_skills/gateways/executor_gateway.py`


## 2. 职责

`ExecutorGateway` 负责抽象并发执行器的创建。

当前核心能力是：

- `create(max_workers)`


## 3. 为什么它有价值

虽然它很小，但 summarize 等流程的并发执行依赖它。

把执行器创建收口后，application 层不需要直接绑定：

- `ThreadPoolExecutor`

这对测试替换和未来实现调整都有帮助。


## 4. 默认实现

默认实现返回：

- `ThreadPoolExecutor`

它是一个典型的“小 gateway，但边界明确”的例子。
