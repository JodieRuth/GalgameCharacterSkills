# Summary 查询接口编排

## 1. 入口文件

- `galgame_character_skills/api/summary_api_service.py`


## 2. 职责

该模块负责两个轻查询接口：

- 扫描已有 summary 角色列表
- 查询某个角色的 summary 文件列表

它本质上是对：

- `files.summary_discovery`
- `workspace` 路径函数

的薄包装。


## 3. 为什么它不进 application

因为这些接口并不执行真正业务流程，它们只是：

- 读取工作区中的现有产物
- 按角色和模式组织结果

所以它们保留在 `api` 层是合理的。


## 4. 设计特点

### 4.1 角色扫描

`scan_summary_roles_result(...)` 会直接调用：

- `discover_summary_roles(...)`

并在返回结果上补 `success=true`。

### 4.2 文件列表

`get_summary_files_result(...)` 使用：

- `require_non_empty_field("role_name", ...)`

在前置校验后调用：

- `find_summary_files_for_role(...)`


## 5. 需要注意的点

这组接口的设计很轻，但它也体现了当前系统的一个现实情况：

- 查询型接口不一定经过 facade

这不是问题本身，但需要在架构文档中持续明确。
