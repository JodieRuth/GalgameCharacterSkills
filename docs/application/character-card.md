# Character Card 用例

## 1. 入口文件

- `galgame_character_skills/application/character_card/service.py`

相关模块：

- `context.py`
- `flow.py`
- `tool_loop.py`
- `output.py`


## 2. 目标

角色卡用例负责基于角色分析结果生成：

- 角色卡 JSON
- 可选的 PNG 封装输出

它和 skills 一样依赖 summarize 的产物，但其流程结构更偏“字段生成”而不是“工具执行结果汇总”。


## 3. 处理阶段

角色卡生成主流程可以拆成：

1. 请求准备
2. 加载角色分析结果
3. 视情况压缩分析上下文
4. 执行角色卡 flow
5. 生成 JSON/PNG 输出
6. 更新 checkpoint 状态


## 4. 请求准备

和其他用例一样，入口通过：

- `prepare_task_context(...)`

恢复时重点回填：

- `fields_data`
- `messages`
- `iteration_count`

这反映了角色卡流程的状态模型是“字段写入状态”。


## 5. 上下文加载

角色卡流程的输入不是 markdown summary，而是分析结果集合：

- `all_character_analyses`
- `all_lorebook_entries`

它们由：

- `load_character_analyses(...)`

负责读取。

之后还可能经过：

- `compress_character_analyses(...)`

进行压缩。


## 6. flow 与 tool loop

角色卡流程的核心执行逻辑当前位于：

- `application/character_card/flow.py`
- `application/character_card/tool_loop.py`

这里有一个重要的架构特点：

- 角色卡的任务级 flow 和字段 loop 已经从 `llm/` 迁移回 `application/character_card/`

这样做是为了避免把任务级 workflow 混进 `llm/` 基础能力层。


## 7. 为什么角色卡没有直接复用通用 tool loop runner

角色卡循环和 skills 循环只有一部分同构。

它还包含几类专有逻辑：

- `fields_data` 快照持久化
- `write_field` 工具调用写回字段
- `is_complete` 触发提前结束
- 无 tool call 时直接解析最终 JSON 内容

因此当前保留独立 loop 是合理的，强行并入共享 runner 反而容易把抽象做坏。


## 8. 输出阶段

flow 完成后，角色卡流程会进入输出收尾：

- 生成 JSON
- 如果有图片和嵌入条件，则生成 PNG
- 写入 cards 工作区目录

这部分逻辑主要集中在：

- `output.py`


## 9. 与 checkpoint 的关系

角色卡的 checkpoint 模型和 skills 类似，都是会话式恢复，但它记录的是：

- 当前会话消息
- 当前已写字段
- 当前迭代次数

这让角色卡恢复时能够从“已经写到哪些字段”继续推进。


## 10. 设计评价

角色卡流程的主要特点：

1. 输入来自 summarize 的分析产物
2. 核心执行形态是字段写入而不是普通工具结果汇总
3. output 阶段明显强于 skills，包含 JSON/PNG 双产物
4. 任务级 workflow 已经被正确收拢到 application 层
