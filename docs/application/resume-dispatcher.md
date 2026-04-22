# 恢复分发器

## 1. 入口文件

- `galgame_character_skills/application/resume_dispatcher.py`


## 2. 职责

`ResumeTaskDispatcher` 负责把：

- 某个 checkpoint 的恢复请求

重新转发回它原本对应的任务入口。

它解决的问题是：

- 恢复是从 `/api/checkpoints/<id>/resume` 进入的
- 但真正恢复执行时，仍应回到 summarize / skills / chara_card 原有主链路


## 3. 处理流程

恢复流程大致如下：

1. 调用 `load_resumable_checkpoint(...)`
2. 检查 checkpoint 是否允许恢复
3. 读取 `task_type`
4. 取出 `input_params`
5. 自动注入 `resume_checkpoint_id`
6. 合并额外覆盖参数
7. 根据 `task_type` 选择 handler
8. 调用对应任务入口


## 4. 为什么它放在 application 层

因为恢复分发不是单纯的 checkpoint 读写能力，也不是 HTTP 入口逻辑。

它本质上是：

- 一个任务级 workflow 决策点

因此它更适合放在 application 层，而不是 routes 或 checkpoint 底层模块。


## 5. 设计价值

这个分发器的最大价值是：

- 恢复并没有另起一套业务流程

而是把请求重新导回原有任务主链路。

这样可以避免：

- 新建执行一套逻辑
- 恢复执行再维护一套逻辑


## 6. 当前约束

当前恢复分发依赖：

- checkpoint 中保存的 `task_type`
- checkpoint 中保存的 `input_params`

这意味着 checkpoint 的数据结构在系统里不是纯粹的“状态存档”，而是“恢复入口的一部分”。


## 7. 设计评价

`ResumeTaskDispatcher` 是一个很值得保留的中间层抽象，因为它清晰地表达了：

- 恢复是任务入口的另一种来源
- 不是底层存储层自己的职责
