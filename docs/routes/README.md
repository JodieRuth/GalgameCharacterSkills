# Routes 层

## 1. 这一层负责什么

`routes/` 是 HTTP 入口层，负责把 Flask URL 规则映射到系统内部的接口处理逻辑。

它的核心职责是：

- 注册路由
- 区分 `GET / POST / DELETE`
- 读取 query、path、file 等入口参数
- 把请求交给 `JsonApiAdapter`
- 将请求转发到 `api` 层或少量查询型 service


## 2. 这一层不负责什么

`routes/` 不应该承担：

- 业务流程编排
- checkpoint 状态恢复细节
- LLM 调用和 tool loop
- 输出文件写入
- 复杂参数清洗和模式分发

如果路由函数开始直接拼多个底层模块，通常意味着职责正在下沉失败。


## 3. 当前路由分组

当前系统按功能分成以下几组：

- `root`
  首页模板入口
- `files`
  文件扫描、上传、token 估算、切片预估
- `summary`
  配置、上下文窗口、summary 查询
- `tasks`
  summarize / skills / chara_card 任务入口
- `checkpoints`
  checkpoint 列表、详情、删除、恢复
- `vndb`
  VNDB 角色查询


## 4. 路由层的统一机制

路由层最重要的统一机制是：

- `JsonApiAdapter`

它统一处理：

- JSON body 读取
- handler 调用
- `dict -> jsonify`

因此大多数路由都呈现出类似模式：

- `adapter.run(...)`
- `adapter.run_with_body(...)`


## 5. 依赖注入方式

路由在注册时拿到显式依赖，而不是从全局位置动态查找对象。

常见形式包括：

- `register_file_routes(app, deps, adapter)`
- `register_task_routes(app, runtime, adapter)`
- `register_checkpoint_routes(app, runtime, adapter)`

这种设计让依赖来源一眼可见，也方便测试时替换。


## 6. 当前组织风格

当前 `routes/` 层存在两种风格：

### 6.1 facade 风格

任务和 checkpoint 相关接口通常会先实例化 facade：

- `TaskApi`
- `CheckpointApi`

然后由 facade 再转发到 application 层。

### 6.2 函数式 service 风格

配置、summary 查询、上下文窗口等接口则更常直接调用函数式 service：

- `get_config_result(...)`
- `scan_summary_roles_result(...)`
- `get_context_limit_result(...)`

这两种方式当前都能工作，但后续需要继续保持边界稳定，避免演变成第三种风格。


## 7. 目录内文档

建议继续阅读：

- `files.md`
- `summaries.md`
- `tasks.md`
- `checkpoints.md`
- `vndb.md`
