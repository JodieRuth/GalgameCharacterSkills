# 文档索引

## 1. 说明

本目录用于维护项目的架构、分层、运行时装配与专题设计文档。

当前文档组织遵循两个原则：

- 以“理解系统”的阅读顺序组织，而不是机械镜像源码目录
- 以稳定的架构主题组织，而不是按单次重构或 commit 临时堆积

现阶段会优先补齐以下几类文档：

- 架构总览与依赖规则
- 运行时装配与请求主链路
- `routes / api / application` 三层职责
- checkpoint、LLM、workspace 等横切专题


## 2. 推荐阅读顺序

首次阅读建议按以下顺序进行：

1. `architecture/overview.md`
2. `architecture/dependency-rules.md`
3. `architecture/runtime-composition.md`
4. `application/README.md`
5. `application/summarize.md`
6. `application/skills.md`
7. `application/character-card.md`
8. `checkpoint/README.md`

目前已完成：

1. `architecture/overview.md`
2. `architecture/dependency-rules.md`
3. `architecture/runtime-composition.md`
4. `architecture/request-lifecycle.md`
5. `routes/*.md`
6. `api/*.md`


## 3. 文档结构约定

文档目录按“总览 + 分层 + 专题”组织。

建议结构如下：

```text
docs/
  README.md
  architecture/
  routes/
  api/
  application/
  domain/
  gateways/
  checkpoint/
  llm/
  files/
  workspace/
  decisions/
  reference/
```

各目录职责：

- `architecture/`
  写系统总览、依赖规则、运行时装配与请求链路
- `routes/`
  写 HTTP 入口层的职责与分组
- `api/`
  写接口编排层、参数校验、任务分发与返回组装
- `application/`
  写核心用例流程与共享机制
- `domain/`
  写稳定的数据结构与领域概念
- `gateways/`
  写基础设施抽象边界
- `checkpoint/`
  写 checkpoint 状态模型、持久化与恢复机制
- `llm/`
  写模型交互能力、prompt 与消息流
- `files/`
  写文件扫描、切片与 summary 发现逻辑
- `workspace/`
  写路径约定、工作区布局与输出目录
- `decisions/`
  写架构决策记录
- `reference/`
  写查表型参考文档


## 4. 每篇文档建议回答的问题

为避免文档风格失控，建议每篇文档尽量覆盖以下问题：

1. 这一层或模块负责什么
2. 它不负责什么
3. 它依赖谁、被谁调用
4. 关键入口文件是什么
5. 核心对象和状态有哪些
6. 当前已知限制或技术债是什么


## 5. 与旧文档的关系

当前仓库中已有：

- `architecture.md`

它仍可作为旧版单文档总览参考，但后续内容会逐步迁移到分层结构下的新文档中。
