# 运行时装配

## 1. 目的

本文档说明系统如何从启动脚本进入 Flask 应用，并在启动时完成：

- 配置预热
- 应用级依赖装配
- 任务运行时装配
- 路由注册
- JSON 响应适配

它回答的问题是：

- 应用是怎么被创建出来的
- 哪些依赖在应用级共享
- 哪些依赖按“任务运行时”暴露给业务流程
- 路由层拿到的 `deps` 和 `runtime` 分别是什么


## 2. 启动入口

本地启动入口是：

- `main.py`

启动顺序如下：

1. 调用 `create_app()`
2. 启动后台线程打开浏览器
3. 使用 `app.run(...)` 启动 Flask 服务

在这个入口里，业务上的真正装配动作都发生在：

- `galgame_character_skills/app.py`


## 3. `create_app()` 的职责

`create_app()` 是整个后端的组合根。

它负责：

1. 预热配置缓存
2. 创建 Flask 应用实例
3. 初始化 CORS
4. 构造应用级依赖 `deps`
5. 构造任务运行时依赖 `runtime`
6. 创建 `JsonApiAdapter`
7. 注册所有路由

当前注册顺序是：

1. `register_root_routes`
2. `register_file_routes`
3. `register_summary_routes`
4. `register_task_routes`
5. `register_checkpoint_routes`
6. `register_vndb_routes`

这里的设计重点是：

- Flask app 只创建一次
- `deps` 用于共享较稳定的应用级对象
- `runtime` 用于承载任务执行所需能力


## 4. 配置预热

在 `create_app()` 最开始会调用：

- `get_app_settings()`

目的不是立即消费配置，而是确保：

- `.env`
- 环境变量
- 默认值

在应用启动期间已经完成加载和缓存，避免第一次请求时才懒加载配置。


## 5. 应用级依赖：`AppDependencies`

应用级依赖由：

- `build_app_dependencies(...)`

构建，当前结构为：

- `file_processor`
- `ckpt_manager`
- `r18_traits`

这些依赖的特点是：

- 生命周期接近整个应用
- 适合作为共享实例
- 被多个路由或任务重复使用

### 5.1 `file_processor`

负责：

- 扫描资源文件
- 保存上传文件
- 计算 token
- 执行切片

它既服务于文件接口，也服务于 summarize 流程。

### 5.2 `ckpt_manager`

负责 checkpoint 的具体存储与状态更新。

在装配阶段它仍是具体实现对象，但不会直接大范围暴露给业务流程，而是会继续包装成 gateway。

### 5.3 `r18_traits`

在启动时加载，用于 VNDB 数据清洗时过滤特征。


## 6. 任务运行时：`TaskRuntimeDependencies`

任务运行时依赖由：

- `build_task_runtime(deps)`

构建，它是 application 层执行任务时最重要的依赖容器。

当前主要包括：

- `file_processor`
- `checkpoint_gateway`
- `storage_gateway`
- `vndb_gateway`
- `executor_gateway`
- `log`
- `clean_vndb_data`
- `get_base_dir`
- `get_workspace_*_dir`
- `estimate_tokens`
- `llm_gateway`
- `tool_gateway`
- `download_vndb_image`
- `embed_json_in_png`

这个结构的设计意图是：

- 让 application 层只依赖能力，不依赖装配细节
- 让测试更容易替换底层实现
- 让运行时依赖关系集中可见


## 7. 为什么要区分 `deps` 和 `runtime`

当前系统把依赖拆成两层：

- `AppDependencies`
- `TaskRuntimeDependencies`

这样做的好处是：

### 7.1 路由层拿到最小需要集

- 文件路由更关心 `file_processor`
- VNDB 路由既需要 `r18_traits`，也需要 `runtime.vndb_gateway`
- 任务路由主要依赖 `runtime`

### 7.2 业务流程不直接依赖具体实现

例如 application 层看到的是：

- `checkpoint_gateway`
- `llm_gateway`
- `storage_gateway`

而不是直接在流程代码里自行创建 manager 或 provider。

### 7.3 测试更容易定制

测试可以：

- 单独替换 `app_dependencies`
- 单独替换 `task_runtime`

从而避免每次都完整初始化真实环境。


## 8. gateway 在装配中的位置

`build_task_runtime()` 会把一部分具体实现包装成默认 gateway：

- `DefaultCheckpointGateway`
- `DefaultStorageGateway`
- `DefaultVndbGateway`
- `DefaultExecutorGateway`
- `DefaultLLMGateway`
- `DefaultToolGateway`

这一步的意义在于：

- 把 application 层依赖的接口固定下来
- 把底层实现替换点集中到装配阶段

也就是说，装配阶段是“具体实现出现最多”的地方，而 application 层应该尽量只看到抽象能力。


## 9. `JsonApiAdapter` 的位置

`JsonApiAdapter` 负责把：

- 请求体读取
- handler 调用
- `dict -> jsonify`

这套样板逻辑统一收口。

当前提供三个入口：

- `body()`
- `response(result)`
- `run(...)`
- `run_with_body(...)`

这使得路由层不需要重复写：

- `request.get_json(...)`
- `jsonify(...)`

同时也保证了接口返回结构统一。


## 10. 路由注册与依赖注入方式

各组路由在注册时拿到不同的依赖：

- `register_root_routes(app)`
- `register_file_routes(app, deps, adapter)`
- `register_summary_routes(app, adapter, get_app_settings)`
- `register_task_routes(app, runtime, adapter)`
- `register_checkpoint_routes(app, runtime, adapter)`
- `register_vndb_routes(app, deps, runtime, adapter)`

这反映了一个很实际的设计选择：

- 不搞全局 service locator
- 在注册阶段显式把所需能力传给路由

这种方式的缺点是函数参数会变多，但优点是依赖来源更清晰。


## 11. 当前设计的优点

当前运行时装配方案的主要优点：

1. 组合根清晰，应用入口集中
2. 应用级依赖和任务级依赖已经分层
3. gateway 抽象在装配阶段落地
4. 路由注册和依赖传递关系直观
5. 测试可以部分替换依赖，减少真实初始化成本


## 12. 当前限制

当前装配仍有几个值得后续继续优化的点：

1. `TaskRuntimeDependencies` 体积已经较大，后续继续增长时需要分组或拆子结构。
2. 某些查询型接口仍有“直接调用函数”和“经由 facade”两种风格并存。
3. 旧文档中的目录说明还没有完全跟上当前装配结构。


## 13. 相关文档

建议继续阅读：

- `request-lifecycle.md`
- `dependency-rules.md`
- `../application/README.md`
- `../gateways/README.md`
