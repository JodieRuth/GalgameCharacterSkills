# Summarize 用例

## 1. 入口文件

- `galgame_character_skills/application/summarize/service.py`

相关模块：

- `checkpoint.py`
- `executor.py`
- `models.py`
- `slice_worker.py`
- `slice_finalize.py`


## 2. 目标

summarize 用例负责把一个或多个输入文本文件处理为角色归纳结果。

根据模式不同，它可以生成：

- 技能生成所需的 markdown summary
- 角色卡生成所需的分析 json


## 3. 处理阶段

summarize 的主流程可以拆成以下阶段：

1. 请求准备
2. 文件切片
3. 切片任务构造
4. 并发执行切片
5. 汇总结果并更新 checkpoint


## 4. 请求准备

这一步通过：

- `_prepare_summarize_request(...)`

调用共享骨架：

- `prepare_task_context(...)`

完成以下动作：

- 从 payload 构造 `SummarizeRequest`
- 构造 LLM 配置
- 创建或恢复 checkpoint
- 执行恢复相关回调
- 做前后置校验

summarize 的校验特点是：

- 新建任务要求 `role_name` 和文件路径
- 恢复任务可从 checkpoint 中回填输入参数


## 5. 文件切片

请求准备完成后，流程会调用：

- `runtime.file_processor.slice_multiple_files(...)`

生成 `current_slices`。

这一步的输出决定了：

- 需要创建多少切片任务
- LLM 请求运行时的请求总数
- checkpoint 的 `total_steps`


## 6. 切片任务构造

每个切片会被包装成：

- `SliceTask`

任务中包含：

- 切片索引
- 切片内容
- 角色名
- instruction
- 输出路径
- 配置
- 模式
- 输出语言
- checkpoint_id

这里 summarize 会根据 `mode` 决定输出扩展名：

- `skills` -> `.md`
- `chara_card` -> `.json`


## 7. 并发执行

切片执行由：

- `execute_slice_tasks(...)`

负责。

这一步通常会：

- 使用请求级 LLM runtime
- 并发调用单片执行逻辑
- 收集 summaries、errors、lorebook entries 等结果

summarize 是当前最典型的“多子任务并发 + 单任务汇总”流程。


## 8. 结果汇总与收尾

收尾阶段由：

- `_finalize_summarize_result(...)`

负责。

它会根据执行结果分三种情况：

### 8.1 全部成功

- `mark_completed`
- 返回成功结果

### 8.2 部分失败

- `mark_failed`
- 返回 `success=true`
- `can_resume=true`

### 8.3 全部失败

- `mark_failed`
- 返回 `success=false`
- `can_resume=true`

这体现了 summarize 一个重要特点：

- “部分完成” 被视为一种可恢复成功态


## 9. summarize 与 checkpoint 的关系

summarize 是 checkpoint 集成最深的一条流程之一：

- 新建时初始化 `pending_items`
- 执行中逐片保存结果
- 恢复时会修正进度状态
- 结束时会根据失败情况决定 `failed/completed`

因此 summarize 也是理解 checkpoint 子系统最好的入口。


## 10. 设计评价

summarize 流程的优点：

1. 结构化程度高
2. 阶段划分清楚
3. 共享准备逻辑和专有执行逻辑边界明确
4. checkpoint 与并发执行的结合较完整

它也是后续新任务流程最值得参考的模板之一。
