# 请求处理主链路

## 1. 目的

本文档描述一次请求从进入 Flask 路由，到进入业务流程，再到返回统一 JSON 结果的主链路。

它主要回答：

- 请求如何穿过 `routes -> api -> application`
- 请求体在哪里读取
- 参数校验发生在哪里
- 任务结果如何包装成统一响应


## 2. 总体路径

当前最常见的 JSON 请求处理链路如下：

`Flask route -> JsonApiAdapter -> api facade / service -> application -> gateway / files / checkpoint / llm -> dict result -> jsonify`

如果是纯查询型接口，链路可能止步于：

`route -> adapter -> api service -> dict result`


## 3. 第一步：进入路由

请求首先进入 `routes/` 下的某个注册函数所绑定的 Flask handler。

例如：

- `/api/summarize`
- `/api/skills`
- `/api/checkpoints/<id>/resume`
- `/api/vndb`

路由层的职责是：

- 选择 URL 和 HTTP method
- 读取 query 参数、path 参数或上传文件
- 把请求转交给 adapter 和下游 handler

路由层不应负责：

- 业务算法
- checkpoint 恢复细节
- LLM 调度逻辑


## 4. 第二步：由 `JsonApiAdapter` 统一读取请求体

对于大多数 JSON `POST` 接口，路由使用：

- `adapter.run_with_body(...)`

处理流程是：

1. `body()` 使用 `request.get_json(silent=True) or {}`
2. 将解析后的 `data` 作为第一个参数传给目标 handler
3. 将 handler 返回的结果交给 `jsonify(...)`

这样做带来的效果是：

- 请求体读取逻辑一致
- 空请求体会被处理成空字典
- 路由代码保持较薄

对于不走 JSON body 的情况：

- 文件上传直接使用 `request.files`
- `GET` 查询接口直接读取 `request.args`


## 5. 第三步：进入 `api` 层

`api/` 层是接口编排层。

它主要负责：

- 参数前置校验
- 按模式或任务类型分发
- 调用 application 层
- 返回统一 `dict` 结构

典型例子：

### 5.1 任务接口

- `TaskApi.summarize(...)`
- `TaskApi.dispatch_skills_mode(...)`
- `TaskApi.generate_character_card(...)`

### 5.2 checkpoint 接口

- `CheckpointApi.list_checkpoints(...)`
- `CheckpointApi.get_checkpoint(...)`
- `CheckpointApi.resume_checkpoint(...)`

### 5.3 函数式查询接口

- `get_config_result(...)`
- `get_context_limit_result(...)`
- `scan_summary_roles_result(...)`
- `get_vndb_info_result(...)`


## 6. 参数校验发生在哪里

当前参数校验主要在 `api/validators.py` 中通过装饰器完成。

常见形式包括：

- `require_non_empty_field(...)`
- `require_condition(...)`

它们通常用于：

- 校验 `role_name`
- 校验 `vndb_id`
- 校验是否选择了文件

校验失败时，不会抛异常，而是直接返回：

```json
{
  "success": false,
  "message": "..."
}
```

这使得路由层和 application 层不必重复处理这些前置错误。


## 7. 第四步：进入 application 层

对于任务型请求，`api` 层会把请求转交给 `application/` 用例层。

application 层负责：

- 请求数据标准化
- checkpoint 创建或恢复
- 业务流程执行
- 调用文件处理、LLM、存储和 gateway
- 构造任务成功或失败结果

三条主要链路分别是：

### 7.1 summarize

`route -> TaskApi.summarize -> run_summarize_task`

### 7.2 skills

`route -> TaskApi.dispatch_skills_mode -> run_generate_skills_task`

### 7.3 character card

`route -> TaskApi.dispatch_skills_mode -> run_generate_character_card_task`


## 8. 任务型请求的典型内部阶段

以 application 层视角看，请求通常会经过以下阶段：

1. 从 payload 构造请求模型
2. 构造 LLM 配置
3. 创建或恢复 checkpoint
4. 执行用例核心逻辑
5. 更新 checkpoint 状态
6. 返回统一结果

其中步骤 1 到 3 在多个任务间已有明显共性，因此当前项目把一部分逻辑抽到了：

- `application/shared/`


## 9. 第五步：访问基础设施能力

application 层执行过程中，会借助 `TaskRuntimeDependencies` 暴露的能力访问基础设施。

常见依赖包括：

- `checkpoint_gateway`
- `storage_gateway`
- `llm_gateway`
- `tool_gateway`
- `executor_gateway`
- `vndb_gateway`
- `file_processor`
- `workspace` 路径函数

这样 application 层看到的是“能力接口”，而不是散落的具体实现对象。


## 10. 第六步：结果构造

系统当前统一使用 `dict` 作为接口响应中间结构。

主要来源有两类：

### 10.1 通用结果

由 `domain/service_result.py` 提供：

- `ok_result(...)`
- `fail_result(...)`

### 10.2 任务结果

由 `application/shared/task_result_factory.py` 提供：

- `ok_task_result(...)`
- `fail_task_result(...)`

这类结果通常包含：

- `success`
- `message`
- `checkpoint_id`
- `can_resume`
- 以及任务特定字段


## 11. 第七步：返回 HTTP 响应

最终返回路由层后，`JsonApiAdapter.response(...)` 会调用：

- `jsonify(result)`

当前实现的重要特点是：

- 业务成功和业务失败大多都返回 HTTP `200`
- 是否成功主要由 JSON 中的 `success` 字段判断

这是一种“统一 JSON 结果优先”的风格，而不是“严格依赖 HTTP 状态码表达业务状态”的风格。


## 12. 三类典型请求链路

### 12.1 查询型接口

例如：

- `/api/config`
- `/api/context-limit`
- `/api/summaries/roles`

链路较短：

`route -> adapter -> api service -> ok_result/fail_result -> jsonify`

### 12.2 任务型接口

例如：

- `/api/summarize`
- `/api/skills`

链路较长：

`route -> adapter -> TaskApi -> application service -> gateways/files/llm/checkpoint -> task_result -> jsonify`

### 12.3 恢复型接口

例如：

- `/api/checkpoints/<id>/resume`

链路带有额外分发：

`route -> adapter -> CheckpointApi.resume_checkpoint -> ResumeTaskDispatcher -> TaskApi -> application service -> jsonify`


## 13. 当前链路设计的优点

当前请求处理链路的主要优点：

1. 路由层较薄，职责相对克制。
2. JSON body 读取和响应包装已经统一收口。
3. 任务型流程大多能稳定落到 application 层。
4. 参数校验和结果组装已有公共模式。


## 14. 当前链路中需要继续收敛的地方

当前仍有几处值得持续关注：

1. 查询型接口中仍同时存在 facade 风格和函数式 service 风格。
2. 部分旧文档仍未完全反映新的 `routes / api / application / gateways` 结构。
3. 某些接口的“返回字段稳定性”还依赖调用方约定，需要后续专题文档继续明确。


## 15. 相关文档

建议继续阅读：

- `runtime-composition.md`
- `dependency-rules.md`
- `../routes/README.md`
- `../api/README.md`
- `../application/README.md`
