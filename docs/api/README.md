# API 编排层

## 1. 这一层负责什么

`api/` 是路由层和 application 层之间的接口编排层。

它主要负责：

- 接收路由层传入的数据
- 执行轻量参数校验
- 根据模式或任务类型做分发
- 调用 application 层或轻查询 service
- 返回统一 `dict` 结构


## 2. 这一层不负责什么

`api/` 不应该承担：

- 长任务流程编排
- checkpoint 状态推进
- LLM 交互
- 输出文件生成

这些都属于 application 或更下层的职责。


## 3. 当前存在的两种组织方式

### 3.1 facade 类

适用于任务型和 checkpoint 型入口：

- `TaskApi`
- `CheckpointApi`

特点是：

- 有状态地持有 `runtime`
- 暴露多组相关接口方法

### 3.2 函数式 service

适用于轻查询与轻编排：

- `file_api_service.py`
- `summary_api_service.py`
- `config_api_service.py`
- `context_api_service.py`
- `vndb_api_service.py`

特点是：

- 单函数输入输出
- 可直接被路由调用


## 4. 与其他层的关系

`api/` 的上下游关系是：

- 上游：`routes/`
- 下游：`application/`、`domain/`，以及少量轻量支撑函数

它不应该反向依赖：

- Flask request/response 对象
- 前端模板


## 5. 统一结果风格

当前 `api/` 层统一返回：

- `ok_result(...)`
- `fail_result(...)`

或下游任务结果工厂构造的 `dict`。

这使得 routes 层只需要负责：

- 调用 handler
- `jsonify(...)`


## 6. 当前值得注意的点

这一层目前整体可用，但需要继续关注：

1. facade 风格和函数式 service 风格并存。
2. 某些旧 service 仍然保留在导出列表中，但新代码已更偏向 facade。
3. 查询型接口是否都值得继续停留在 `api/` 层，需要后续逐步统一判断标准。


## 7. 目录内文档

建议继续阅读：

- `task-api.md`
- `checkpoint-api.md`
- `file-api.md`
- `summary-api.md`
- `config-and-context-api.md`
- `vndb-api.md`
