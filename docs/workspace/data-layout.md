# 工作区数据布局

## 1. 主要目录

当前工作区中最重要的目录包括：

- `resource/`
- `uploads/`
- `summaries/`
- `skills/`
- `cards/`
- `checkpoints/`


## 2. 目录含义

### 2.1 `resource/`

输入文本资源。

这是当前实际接入 Web 上传与文件扫描流程的输入目录。

### 2.2 `uploads/`

工作区路径规则中定义的上传目录。

当前版本中，这个目录主要体现为路径约定和预留结构，尚未接入实际输入主流程；实际输入仍然使用 `resource/`。

### 2.3 `summaries/`

summarize 产物，包括：

- markdown summary
- character-card 分析 json

### 2.4 `skills/`

技能包生成结果。

### 2.5 `cards/`

角色卡 JSON / PNG 输出。

### 2.6 `checkpoints/`

任务状态和恢复数据。


## 3. 设计意义

当前数据布局是整个系统“以文件系统为工作区”的基础约定。

`files/`、`application/`、`checkpoint/`、`summary discovery` 都依赖这套布局保持一致。
