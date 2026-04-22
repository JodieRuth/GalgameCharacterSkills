# 工作区数据布局

## 1. 主要目录

当前工作区中最重要的目录包括：

- `resource/`
- `summaries/`
- `skills/`
- `cards/`
- `checkpoints/`


## 2. 目录含义

### 2.1 `resource/`

输入文本资源。

### 2.2 `summaries/`

summarize 产物，包括：

- markdown summary
- character-card 分析 json

### 2.3 `skills/`

技能包生成结果。

### 2.4 `cards/`

角色卡 JSON / PNG 输出。

### 2.5 `checkpoints/`

任务状态和恢复数据。


## 3. 设计意义

当前数据布局是整个系统“以文件系统为工作区”的基础约定。

`files/`、`application/`、`checkpoint/`、`summary discovery` 都依赖这套布局保持一致。
