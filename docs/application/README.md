# Application 层

## 1. 这一层负责什么

`application/` 是项目的核心用例层，负责真正的业务流程编排。

在当前项目中，它主要承载：

- summarize 用例
- 技能生成用例
- 角色卡生成用例
- 共享任务准备逻辑
- 共享结果组装逻辑
- 恢复分发与通用 tool loop 支撑


## 2. 这一层不负责什么

`application/` 不应直接承担：

- HTTP 路由与请求对象处理
- 前端模板渲染
- provider 级别的模型交互细节
- 底层存储实现细节

它应该依赖的是“能力接口”和“支撑模块”，而不是入口协议和框架对象。


## 3. 这一层为什么是系统核心

如果把整个系统分成“接入口”和“做事情”两部分，那么 `application/` 就是后者。

它决定了：

- 请求如何被解释为任务
- checkpoint 如何被创建与恢复
- 文件、LLM、gateway 何时被调用
- 成功、部分成功、失败如何返回

也就是说，这一层定义的是“系统真正做什么”。


## 4. 当前目录结构

当前 `application/` 主要由以下部分组成：

- `app_container.py`
  运行时依赖装配入口
- `shared/`
  任务准备、结果工厂、恢复状态等共性能力
- `summarize/`
  文本归纳用例
- `skills/`
  技能生成用例
- `character_card/`
  角色卡生成用例
- `resume_dispatcher.py`
  恢复请求分发
- `tool_loop_runner.py`
  通用 checkpointed tool loop 骨架
- `compression_*`
  压缩策略相关辅助能力


## 5. 与其他层的关系

上游：

- `api/`

下游：

- `domain/`
- `gateways/`
- `checkpoint/`
- `files/`
- `llm/`
- `workspace/`

`application/` 是“把下游能力组织成业务流程”的地方。


## 6. 当前设计特点

### 6.1 共享准备逻辑已经抽出

多个任务共用：

- 请求模型构造
- checkpoint 创建/恢复
- 恢复状态注入
- 统一结果工厂

这些逻辑已经集中在 `shared/` 中，这是当前架构里比较健康的一部分。

### 6.2 任务目录按用例拆分

而不是按技术细节拆分。

这带来的好处是：

- summarize、skills、character-card 的边界更明确
- 阅读和维护更贴近业务流程

### 6.3 运行时依赖集中暴露

`TaskRuntimeDependencies` 让业务流程可以只依赖能力，不依赖装配细节。


## 7. 当前需要继续注意的点

1. `TaskRuntimeDependencies` 规模已经较大，后续继续增长时需要考虑分组。
2. 某些能力仍然分散在 `application`、`llm`、`checkpoint` 多个目录之间，需要持续维护清晰边界。
3. 共享骨架的抽象粒度需要控制，避免为了复用而过度参数化。


## 8. 目录内文档

建议继续阅读：

- `shared.md`
- `resume-dispatcher.md`
- `summarize.md`
- `skills.md`
- `character-card.md`
