# Checkpoint 恢复机制

## 1. 恢复入口

恢复入口最终由：

- `/api/checkpoints/<id>/resume`

触发。

但 checkpoint 子系统内部首先要做的是：

- 判断这个 checkpoint 是否“允许恢复”

相关逻辑位于：

- `checkpoint/resume.py`


## 2. 恢复判断的目标

恢复机制要回答两个问题：

1. 这个 checkpoint 是否存在
2. 这个 checkpoint 当前状态是否允许恢复


## 3. 当前约束

当前设计下，一般只有：

- `failed`

状态的任务才是恢复入口的主要对象。

而：

- `running`
- `completed`

通常不允许恢复。


## 4. 恢复不是直接执行底层逻辑

checkpoint 子系统本身不负责真正恢复某个具体业务流程。

它提供的是：

- 恢复前检查
- 恢复所需的状态数据

之后会由：

- `ResumeTaskDispatcher`

将恢复请求重新导回对应任务主链路。


## 5. 恢复时回填什么

恢复时一般会回填：

- `input_params`
- `resume_checkpoint_id`
- 任务专属的 LLM 状态

例如：

- summarize 恢复切片进度
- skills 恢复 messages / iteration / all_results
- character-card 恢复 messages / fields_data / iteration_count


## 6. 设计价值

当前恢复机制的价值在于：

- 没有为“恢复执行”单独造一套任务实现
- 而是把它重新接回原有业务流程

这让系统的正确性更容易维护。
