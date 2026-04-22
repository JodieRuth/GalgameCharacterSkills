# 术语表

## summarize

将原始文本切片后交给模型进行归纳分析的任务。

## skills

基于 summarize 结果生成技能包的任务。

## chara_card

基于分析结果生成角色卡 JSON/PNG 的任务。

## checkpoint

用于保存任务状态和恢复信息的本地持久化对象。

## gateway

application 层依赖的基础设施能力抽象。

## workflow

一个任务从输入到输出的完整业务流程。

## prepared

共享任务准备阶段产出的中间对象，通常包含请求模型、配置、checkpoint 信息和恢复状态。
