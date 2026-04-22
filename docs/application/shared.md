# Application 共享机制

## 1. 范围

共享机制主要位于：

- `galgame_character_skills/application/shared/`

它负责为多条任务流程提供横切支持。


## 2. 为什么要有 shared

summarize、skills、character-card 三条流程虽然业务目标不同，但都存在明显共性：

- 从 payload 构造请求模型
- 构造 LLM 配置
- 创建或恢复 checkpoint
- 注入恢复状态
- 记录恢复日志
- 统一包装结果

如果这些逻辑散落在各个 service 里，重复会很快增多。


## 3. 主要能力

### 3.1 `task_prepare_context.py`

这是 shared 中最关键的模块。

它提供：

- `prepare_task_context(...)`
- payload loader builder
- prepared builder
- 恢复回调 builder

它的作用是把“任务准备阶段”收敛成统一骨架。

### 3.2 `checkpoint_prepare.py`

负责：

- 创建新 checkpoint
- 加载可恢复 checkpoint
- 产出统一的 checkpoint 准备结果

### 3.3 `task_prepared.py`

定义 prepared 数据结构，用来承接：

- request_data
- config
- checkpoint_id
- 恢复状态字段

### 3.4 `task_result_factory.py`

提供：

- `ok_task_result(...)`
- `fail_task_result(...)`

用于统一任务返回结构。

### 3.5 `task_state.py`

定义 summarize、skills、character-card 各自的恢复状态模型。

### 3.6 `runtime_logging.py`

提供 runtime 级日志写入辅助，用于恢复提示等轻量日志。


## 4. `prepare_task_context(...)` 的价值

这是当前 application 层里最有代表性的共享抽象。

它负责把以下动作串起来：

1. 解析请求 payload
2. 前置校验
3. 构造配置
4. 准备 checkpoint
5. 注入恢复状态
6. 执行恢复后回调
7. 后置校验
8. 产出 prepared 对象

这让各任务 service 可以更专注于自己的核心执行阶段。


## 5. 共享抽象的边界

shared 的价值是去重，但边界必须克制。

它适合抽：

- 任务准备阶段共性
- 结果组装共性
- 状态映射共性

它不适合抽：

- summarize/skills/chara_card 特有业务规则
- 某条流程的输出文件命名
- 某条流程的特定 tool loop 细节


## 6. 当前设计评价

当前 `shared/` 的整体方向是正确的，因为它抽出的都是“流程骨架级共性”。

真正需要警惕的是：

- 为了复用而把各条流程的特殊逻辑也抽到 shared

一旦发生这种情况，shared 会变成难维护的大杂烩。
