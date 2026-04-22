# Files 路由组

## 1. 范围

本组路由覆盖：

- `GET /api/files`
- `POST /api/files/upload`
- `POST /api/files/tokens`
- `POST /api/slice`

入口代码位于：

- `galgame_character_skills/routes/files.py`


## 2. 职责

这一组路由负责“文件输入侧”的能力，包括：

- 扫描工作区中的文本文件
- 接收文件上传
- 对文件做 token 估算
- 对选中文件做切片预估

这些接口都不真正执行 summarize 任务，它们更偏向前置准备与信息查询。


## 3. 依赖

该路由组注册时依赖：

- `deps.file_processor`
- `adapter`

它不直接依赖：

- `runtime`
- `checkpoint`
- `llm`

这也说明它属于相对轻量的一组接口。


## 4. 处理方式

### 4.1 扫描文件

`/api/files` 直接调用：

- `scan_files_result(file_processor)`

返回资源目录中的文件列表。

### 4.2 上传文件

`/api/files/upload` 是一个特殊接口：

- 使用 `multipart/form-data`
- 直接从 `request.files` 读取文件
- 不走 `run_with_body(...)`

这也是当前 routes 层里少数直接处理上传对象的地方。

### 4.3 token 估算

`/api/files/tokens` 通过 `adapter.run_with_body(...)` 读取 JSON body，再转发到：

- `calculate_tokens_result(...)`

### 4.4 切片预估

`/api/slice` 同样通过 JSON body 调用：

- `slice_file_result(...)`

该接口会借助：

- `extract_file_paths(...)`

兼容 `file_path` 和 `file_paths` 两种输入方式。


## 5. 设计特点

这组路由有几个明显特点：

1. 绝大多数逻辑仍保持在薄路由 + 薄 API service 模式。
2. 上传接口因为请求格式不同，在路由里直接读取 `request.files`。
3. 它主要依赖 `FileProcessor`，不引入更复杂的 task runtime。


## 6. 边界判断

如果这组路由后续开始直接做：

- 文件持久化策略分支
- summarize 预处理流程
- checkpoint 状态管理

那就说明职责越界了。这些内容应继续留在 `api` 或 `application` 层。
