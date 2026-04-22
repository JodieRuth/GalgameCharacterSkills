# CheckpointGateway

## 1. 入口文件

- `galgame_character_skills/gateways/checkpoint_gateway.py`


## 2. 职责

`CheckpointGateway` 定义了 application 层访问 checkpoint 子系统的稳定接口。

它覆盖的能力包括：

- 创建 checkpoint
- 加载 checkpoint
- 更新进度
- 保存切片结果
- 保存/读取 LLM 状态
- 标记完成/失败
- 列表查询
- 删除
- 获取临时目录


## 3. 为什么它很关键

在当前项目中，checkpoint 是横切能力。

如果 application 层直接到处依赖：

- `CheckpointManager`

那么：

- 测试替换成本高
- 存储后端很难调整
- 边界会不断被绕过

因此 `CheckpointGateway` 是最重要的 gateway 之一。


## 4. 默认实现

- `DefaultCheckpointGateway`

当前只是把调用委托给：

- `CheckpointManager`

这说明当前抽象成本低，但边界价值很高。


## 5. 当前设计评价

这条边界当前已经基本成立，后续应继续坚持：

- 任务流程优先经由 gateway，而不是直接 new manager
