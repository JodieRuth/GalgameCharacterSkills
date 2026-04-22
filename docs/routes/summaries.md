# Summary 与配置路由组

## 1. 范围

本组路由覆盖：

- `GET /api/config`
- `GET /api/summaries/roles`
- `POST /api/summaries/files`
- `POST /api/context-limit`

入口代码位于：

- `galgame_character_skills/routes/summary.py`


## 2. 职责

这组路由承担两类轻查询接口：

- 配置与模型上下文查询
- summary 文件和角色列表查询

它们有一个共同特点：

- 都不是长任务
- 不需要 checkpoint
- 不需要进入完整 application workflow


## 3. 当前组织方式

这一组路由基本采用“函数式 service”模式，而不是 facade 模式。

例如：

- `get_config_result(...)`
- `scan_summary_roles_result(...)`
- `get_summary_files_result(...)`
- `get_context_limit_result(...)`

它们直接被路由调用，再由 adapter 统一包装。


## 4. 为什么没有统一走 facade

因为这组接口的业务形态比较简单：

- 输入少
- 输出轻
- 没有复杂流程状态

在这种情况下，单独为每类查询再包装 facade，收益并不高。

但需要注意，当前项目里这也意味着 routes 层和 api 层存在两种组织风格并存。


## 5. 依赖关系

本组路由会直接接触以下支撑模块：

- `get_app_settings`
- `discover_summary_roles`
- `find_summary_files_for_role`
- `get_workspace_summaries_dir`
- `get_model_context_limit`

这说明它比任务型路由更贴近查询支撑模块，而不是任务执行框架。


## 6. 风险与约束

这组路由虽然简单，但后续要注意两点：

1. 不要在这里继续长出复杂业务流程，否则应该切回 facade/application 模式。
2. 文档和代码要明确说明：这是一组“轻查询接口”，不是新的第三层业务逻辑入口。
