# Checkpoint 子系统

## 1. 这一组文档负责什么

`checkpoint/` 子系统负责：

- 创建任务 checkpoint
- 持久化任务状态
- 持久化切片结果
- 持久化 LLM 会话状态
- 列表查询与详情查询
- 删除 checkpoint 及临时目录
- 为恢复执行提供输入


## 2. 为什么 checkpoint 值得单独成组

checkpoint 不是一个普通工具模块，它横跨：

- summarize
- skills
- character-card

并且直接影响：

- 任务可恢复性
- 部分完成语义
- 前端任务列表展示
- 长流程失败后的继续执行

所以它应该被当作独立子系统理解，而不是零散文件读写逻辑。


## 3. 核心组成

当前 `checkpoint/` 目录主要包括：

- `store.py`
  底层 JSON 文件存储
- `progress.py`
  进度与状态更新
- `llm_state.py`
  LLM 会话状态存储
- `slice_results.py`
  切片结果保存与读取
- `query.py`
  列表与概览查询
- `cleanup.py`
  删除和清理
- `resume.py`
  恢复可行性检查
- `manager.py`
  聚合入口


## 4. 与 application 的关系

application 层并不应处处直接依赖 `CheckpointManager`。

更健康的使用方式是：

- 通过 `CheckpointGateway`
- 或通过统一恢复入口

也就是说：

- `checkpoint/` 提供能力
- `application/` 决定何时使用这些能力


## 5. 目录内文档

建议继续阅读：

- `state-model.md`
- `persistence.md`
- `resume.md`
- `progress-and-slices.md`
