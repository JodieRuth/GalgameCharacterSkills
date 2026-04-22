# 任务类型常量

## 1. 核心文件

- `domain/task_types.py`


## 2. 当前任务类型

当前系统中最核心的任务类型包括：

- `summarize`
- `generate_skills`
- `generate_chara_card`


## 3. 这些常量为什么重要

它们不仅用于业务判断，还直接参与：

- checkpoint 创建
- 恢复分发
- 任务列表过滤

因此它们是系统内非常重要的“枚举级契约”。
