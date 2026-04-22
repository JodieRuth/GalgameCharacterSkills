# Files 支撑层

## 1. 这一层负责什么

`files/` 目录负责：

- 资源文本扫描
- 文件上传保存
- token 计算
- 文本切片
- summary 目录发现


## 2. 这一层不负责什么

它不负责任务调度、checkpoint 或 LLM。

它更像是“输入和产物发现支撑层”。


## 3. 核心模块

- `processor.py`
- `summary_discovery.py`


## 4. 目录内文档

建议继续阅读：

- `processor.md`
- `summary-discovery.md`
