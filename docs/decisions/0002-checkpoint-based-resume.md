# 0002 基于 Checkpoint 的恢复机制

## 背景

summarize、skills、character-card 都属于可能长时间运行且容易中断的任务。

## 决策

使用本地 checkpoint 文件保存：

- 输入参数
- 任务进度
- 中间结果
- LLM 会话状态

并通过统一恢复入口重新导回任务主链路。

## 影响

- 任务可以失败后继续执行
- checkpoint 成为横切子系统
- 任务实现需要考虑恢复状态
