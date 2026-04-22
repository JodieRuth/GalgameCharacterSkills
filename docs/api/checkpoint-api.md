# CheckpointApi

## 1. 入口文件

- `galgame_character_skills/api/checkpoint_api.py`


## 2. 职责

`CheckpointApi` 是 checkpoint 相关接口的 facade。

它负责：

- 列表查询
- 详情查询
- 删除
- 恢复分发


## 3. 为什么需要 facade

checkpoint 接口虽然表面上只是 CRUD + resume，但恢复逻辑其实会牵涉：

- checkpoint 状态读取
- 任务类型判断
- 恢复参数合并
- 分发回相应任务入口

把这些逻辑放进 facade 后，路由层可以保持简单。


## 4. `ResumeTaskDispatcher`

`CheckpointApi` 内部最重要的协作者是：

- `ResumeTaskDispatcher`

它会根据 checkpoint 中记录的 `task_type`，将恢复请求分发到：

- summarize
- generate_skills
- generate_chara_card

对应 handler 映射由：

- `build_resume_task_handlers(...)`

生成。


## 5. 列表与详情接口的风格

### 5.1 列表

调用：

- `runtime.checkpoint_gateway.list_checkpoints(...)`

然后包装成：

- `ok_result(checkpoints=...)`

### 5.2 详情

调用：

- `load_checkpoint(...)`
- `load_llm_state(...)`

组合成统一详情结果。


## 6. 恢复接口的职责边界

`resume_checkpoint(...)` 本身不执行具体业务流程，它只负责：

1. 读取 checkpoint
2. 合并恢复参数
3. 交给 dispatcher

真正的 summarize / skills / chara_card 执行，仍发生在 application 层。


## 7. 设计评价

`CheckpointApi` 的设计优点：

1. 把恢复逻辑从路由层拿走
2. 把 checkpoint 查询和恢复入口集中
3. 让“恢复”这件事仍然回到原有任务主链路，而不是另起一套执行方式
