# Skills 用例

## 1. 入口文件

- `galgame_character_skills/application/skills/service.py`

相关模块：

- `context.py`
- `tool_loop.py`
- `finalize.py`


## 2. 目标

skills 用例负责基于已生成的角色 summary 文件，驱动 LLM 生成技能包产物。

这条流程的核心特征是：

- 输入不是原始文本
- 而是 summarize 的产物


## 3. 处理阶段

技能生成主流程可以拆成：

1. 请求准备
2. 查找 summary 文件
3. 构建技能生成上下文
4. 初始化 tool loop
5. 执行 checkpointed tool loop
6. finalize 输出


## 4. 请求准备

与其他任务一样，skills 通过：

- `prepare_task_context(...)`

完成：

- payload -> `GenerateSkillsRequest`
- 配置构造
- checkpoint 新建或恢复
- 恢复状态注入

它恢复时重点回填的状态包括：

- `messages`
- `all_results`
- `iteration`


## 5. 查找输入

skills 不直接处理原始文本，它首先会在 summaries 工作区中查找：

- 当前角色的 markdown summary 文件

如果找不到，任务直接失败。

这意味着 skills 对 summarize 结果存在显式依赖。


## 6. 构建上下文

上下文构建由：

- `build_skill_context(...)`

负责。

这一步通常会处理：

- summary 文件读取
- 上下文压缩判断
- prompt 输入文本准备

在技能生成里，上下文是否需要压缩是重要决策点之一。


## 7. tool loop

skills 流程的中段核心是：

- 初始化对话和工具
- 执行 checkpointed tool loop

当前它通过：

- `initialize_skill_generation(...)`
- `run_skill_tool_loop(...)`

接上通用骨架：

- `application/tool_loop_runner.py`

这意味着 skills 的循环骨架比角色卡流程更通用、更接近共享 runner 的抽象模型。


## 8. finalize

tool loop 完成后，流程会进入：

- `finalize_generate_skills(...)`

这里负责：

- 落盘技能产物
- 写入输出目录
- 更新最终结果

skills 的最终产出通常会落到：

- skills 工作区目录


## 9. 与 checkpoint 的关系

skills 的 checkpoint 重点不在“切片进度”，而在：

- tool loop 迭代状态
- messages
- all_results

这和 summarize 的“多片并发”是不同类型的状态模型。


## 10. 设计评价

skills 用例的特点是：

1. 明显依赖 summarize 结果
2. 核心复杂度集中在上下文构建和 tool loop
3. 状态模型偏会话式，而不是切片式

它很适合作为“单上下文、迭代式生成流程”的代表。
