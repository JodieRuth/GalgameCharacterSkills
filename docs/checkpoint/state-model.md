# Checkpoint 状态模型

## 1. 顶层结构

一个 checkpoint 当前通常包含以下顶层字段：

- `checkpoint_id`
- `task_type`
- `status`
- `created_at`
- `updated_at`
- `input_params`
- `progress`
- `intermediate_results`
- `llm_conversation_state`
- `metadata`

其中最关键的是：

- `status`
- `progress`
- `llm_conversation_state`


## 2. `status`

当前常见状态包括：

- `running`
- `failed`
- `completed`

这些状态同时影响：

- 前端任务列表展示
- 是否允许恢复
- 最终执行结果语义


## 3. `progress`

`progress` 用于表达任务的阶段性推进情况，常见字段包括：

- `current_step`
- `total_steps`
- `current_phase`
- `completed_items`
- `failed_items`
- `pending_items`
- `error_message`

不同任务会以不同方式使用这些字段。

### 3.1 summarize

更偏向：

- 多切片进度
- `completed_items / pending_items`

### 3.2 skills / character-card

更偏向：

- 当前阶段
- 当前迭代
- 是否可恢复


## 4. `intermediate_results`

当前主要用于保存：

- 切片输出
- 临时文件
- 最终输出路径

它的作用是让任务在中途中断后，仍然能找到已生成的中间产物。


## 5. `llm_conversation_state`

这是 checkpoint 中最特殊的一块状态，负责保存：

- `messages`
- `tool_call_history`
- `last_response`
- `iteration_count`
- `all_results`
- `fields_data`

不同任务对这块状态的使用方式不同：

- skills 更关注 `messages / all_results / iteration_count`
- character-card 更关注 `messages / fields_data / iteration_count`


## 6. 为什么一个 checkpoint 需要同时存业务状态和会话状态

因为当前系统的恢复目标不仅是“知道任务做没做完”，还包括：

- 能不能接着跑
- 从哪个阶段接着跑
- LLM 会话是否能继续

这也是 checkpoint 设计比普通任务表更复杂的原因。
