# 0003 TaskApi 统一任务入口

## 背景

随着 summarize、skills、character-card 三条主流程出现，路由层需要一个稳定的任务入口组织方式。

## 决策

引入：

- `TaskApi`

作为任务 facade，并用：

- `/api/skills + mode`

统一技能包和角色卡生成入口。

## 影响

- 路由层更薄
- 任务入口集中
- `mode` 成为接口语义的一部分
