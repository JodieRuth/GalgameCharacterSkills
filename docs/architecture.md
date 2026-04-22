# GalgameCharacterSkills 架构入口

## 1. 说明

本文件不再承担“单文档描述整个系统”的职责。

原因是当前项目已经包含：

- 多条核心任务流程
- checkpoint 横切子系统
- 多层目录边界
- 较多基础设施抽象

继续把所有设计都堆在一个文件里，会很快出现两个问题：

1. 内容难以维护，容易滞后于代码
2. 不同层次的信息混在一起，阅读成本高

因此，从当前版本开始：

- `docs/architecture.md` 保留为兼容入口
- 具体架构内容迁移到 `docs/` 下的分层文档树


## 2. 推荐阅读入口

如果你是第一次阅读项目架构，建议按以下顺序开始：

1. [docs/README.md](/D:/AI/GalgameCharacterSkills/docs/README.md)
2. [overview.md](/D:/AI/GalgameCharacterSkills/docs/architecture/overview.md)
3. [dependency-rules.md](/D:/AI/GalgameCharacterSkills/docs/architecture/dependency-rules.md)
4. [runtime-composition.md](/D:/AI/GalgameCharacterSkills/docs/architecture/runtime-composition.md)
5. [request-lifecycle.md](/D:/AI/GalgameCharacterSkills/docs/architecture/request-lifecycle.md)


## 3. 文档结构

当前架构文档按“总览 + 分层 + 专题 + 参考”组织：

```text
docs/
  README.md
  architecture/
  routes/
  api/
  application/
  checkpoint/
  gateways/
  llm/
  files/
  workspace/
  domain/
  decisions/
  reference/
```


## 4. 分层文档导航

### 4.1 架构总览

- [overview.md](/D:/AI/GalgameCharacterSkills/docs/architecture/overview.md)
- [dependency-rules.md](/D:/AI/GalgameCharacterSkills/docs/architecture/dependency-rules.md)
- [runtime-composition.md](/D:/AI/GalgameCharacterSkills/docs/architecture/runtime-composition.md)
- [request-lifecycle.md](/D:/AI/GalgameCharacterSkills/docs/architecture/request-lifecycle.md)

### 4.2 HTTP 入口与接口编排

- [routes/README.md](/D:/AI/GalgameCharacterSkills/docs/routes/README.md)
- [api/README.md](/D:/AI/GalgameCharacterSkills/docs/api/README.md)

### 4.3 核心业务流程

- [application/README.md](/D:/AI/GalgameCharacterSkills/docs/application/README.md)
- [summarize.md](/D:/AI/GalgameCharacterSkills/docs/application/summarize.md)
- [skills.md](/D:/AI/GalgameCharacterSkills/docs/application/skills.md)
- [character-card.md](/D:/AI/GalgameCharacterSkills/docs/application/character-card.md)

### 4.4 横切子系统

- [checkpoint/README.md](/D:/AI/GalgameCharacterSkills/docs/checkpoint/README.md)
- [gateways/README.md](/D:/AI/GalgameCharacterSkills/docs/gateways/README.md)
- [llm/README.md](/D:/AI/GalgameCharacterSkills/docs/llm/README.md)
- [workspace/README.md](/D:/AI/GalgameCharacterSkills/docs/workspace/README.md)

### 4.5 稳定契约与参考

- [domain/README.md](/D:/AI/GalgameCharacterSkills/docs/domain/README.md)
- [api-contract.md](/D:/AI/GalgameCharacterSkills/docs/reference/api-contract.md)
- [checkpoint-schema.md](/D:/AI/GalgameCharacterSkills/docs/reference/checkpoint-schema.md)
- [glossary.md](/D:/AI/GalgameCharacterSkills/docs/reference/glossary.md)

### 4.6 架构决策记录

- [0001-layered-architecture.md](/D:/AI/GalgameCharacterSkills/docs/decisions/0001-layered-architecture.md)
- [0002-checkpoint-based-resume.md](/D:/AI/GalgameCharacterSkills/docs/decisions/0002-checkpoint-based-resume.md)
- [0003-task-api-dispatch.md](/D:/AI/GalgameCharacterSkills/docs/decisions/0003-task-api-dispatch.md)
- [0004-move-character-card-flow-to-application.md](/D:/AI/GalgameCharacterSkills/docs/decisions/0004-move-character-card-flow-to-application.md)


## 5. 当前系统的最小摘要

如果只需要一句话概括当前架构，可以理解为：

`routes -> api -> application -> domain`

并由以下支撑层协作：

- `gateways`
- `checkpoint`
- `llm`
- `files`
- `workspace`

其中：

- `routes` 负责 HTTP 入口
- `api` 负责接口编排
- `application` 负责用例流程
- `domain` 负责稳定契约


## 6. 本文件后续维护策略

后续原则如下：

1. 本文件只维护导航和最小摘要。
2. 具体实现细节不再回填到本文件。
3. 新增架构内容时，优先写入对应目录下的专题文档。
4. 如果目录结构变化，应优先更新本文件中的导航链接和 `docs/README.md`。
