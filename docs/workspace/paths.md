# Workspace 路径规则

## 1. 核心文件

- `workspace/paths.py`


## 2. 工作区根目录

工作区根目录由：

- `get_workspace_root()`

统一计算。

它会读取：

- `settings.workspace_dir`

并结合：

- `get_base_dir()`

决定最终根路径。


## 3. 路径计算规则

当前规则是：

- 若 `workspace_dir` 为空，默认使用项目根目录
- 若 `workspace_dir` 为绝对路径，直接使用
- 若 `workspace_dir` 为相对路径，则基于项目根目录拼接


## 4. 子目录函数

当前公开的子目录包括：

- `uploads`
- `summaries`
- `skills`
- `cards`
- `checkpoints`

application 和 checkpoint 等模块都应优先通过这些函数获取路径，而不是手工拼接。
