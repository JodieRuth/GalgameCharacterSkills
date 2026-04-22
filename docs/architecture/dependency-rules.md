# 分层依赖规则

## 1. 目的

本文档用于定义项目内主要目录的依赖方向和职责边界，避免代码在继续演进时重新退化为“所有模块互相调用”的结构。

规则的核心目标有两个：

- 保持业务流程入口清晰
- 保持基础设施替换与测试隔离的可能性


## 2. 顶层依赖方向

推荐依赖方向如下：

`routes -> api -> application -> domain`

同时：

- `application -> gateways`
- `application -> files / checkpoint / llm / workspace`
- `gateways -> 具体实现`

可以把它理解为：

- `routes` 负责接请求
- `api` 负责接口编排
- `application` 负责业务流程
- `domain` 负责稳定的数据契约
- `gateways` 负责隔离基础设施


## 3. 各层职责与允许依赖

### 3.1 `routes/`

职责：

- 注册 HTTP 路由
- 获取 query / body / file 参数
- 调用 `api` facade 或查询 service

允许依赖：

- `api/`
- 少量稳定的配置或适配器

不应依赖：

- 复杂业务流程实现细节
- 具体 checkpoint 存储细节
- 具体 LLM 交互细节


### 3.2 `api/`

职责：

- 参数校验
- 模式分发
- 对外返回统一结果结构
- 对路由层屏蔽下游用例细节

允许依赖：

- `application/`
- `domain/`
- 少量工具型校验逻辑

不应依赖：

- 具体路由对象或 Flask 细节
- 与自身职责无关的底层实现拼装


### 3.3 `application/`

职责：

- 实现完整用例流程
- 编排 checkpoint、LLM、存储和文件处理
- 统一处理任务准备、恢复和结果收尾

允许依赖：

- `domain/`
- `gateways/`
- `checkpoint/`
- `files/`
- `llm/`
- `workspace/`
- 与具体用例强相关的稳定支撑模块

不应依赖：

- `routes/`
- HTTP 请求对象
- 前端展示逻辑


### 3.4 `domain/`

职责：

- 定义任务请求模型
- 定义任务类型
- 定义统一结果结构

允许依赖：

- 尽量只依赖标准库

不应依赖：

- `routes/`
- `api/`
- `application/`
- Flask、LLM provider、文件系统实现等外部层


### 3.5 `gateways/`

职责：

- 抽象基础设施能力边界
- 为 application 提供稳定接口

允许依赖：

- 对应的具体实现模块
- 标准库

不应依赖：

- `routes/`
- HTTP 入口层
- 与网关职责无关的业务流程


## 4. 特殊子系统的边界

### 4.1 `checkpoint/`

`checkpoint/` 是基础设施子系统，但它不是通用工具库，而是业务流程强相关的状态持久化机制。

约束：

- `application` 可以通过 `checkpoint_gateway` 或稳定接口使用它
- 不应由上层到处直接 new 具体 manager 并绕过统一依赖注入


### 4.2 `llm/`

`llm/` 应尽量只承载：

- 模型交互
- prompt 构造
- 消息流
- provider 配置

不应长期承载：

- 任务级 workflow
- 明显属于 application 层的恢复编排逻辑


### 4.3 `files/` 与 `workspace/`

这两个目录是支撑模块：

- `files/` 负责文本输入和 summary 发现
- `workspace/` 负责工作区路径与目录约定

它们可以被 `application` 使用，但不应反向依赖 `application`


## 5. 当前项目中的推荐执行规则

为降低边界继续漂移的风险，建议后续开发遵循以下规则：

1. 新 HTTP 接口优先经由 `api` 层暴露，不直接在 `routes` 中拼装复杂业务流程。
2. 新任务流程优先落在 `application/`，不要直接放进 `llm/` 或其他基础设施目录。
3. 需要替换或 mock 的能力优先抽象进 `gateways/`。
4. checkpoint 状态保存优先通过注入能力完成，不要在流程代码中绕过网关直接绑定具体实现。
5. `domain/` 中的对象应尽量保持小而稳定，避免混入执行逻辑。


## 6. 违反规则时的判断标准

如果新增代码出现以下特征，通常意味着边界正在变差：

- 路由函数开始直接调用多个底层模块拼装业务结果
- `llm/` 内出现完整任务恢复、输出落盘或 checkpoint 状态推进逻辑
- `application/` 直接依赖具体 Flask 对象
- `domain/` 开始依赖外部服务或文件系统
- 某个流程为了省事绕过 gateway 直接绑定具体实现


## 7. 与后续文档的关系

本文档只定义依赖规则，不解释具体流程。

后续应由以下文档补充细节：

- `overview.md`
  解释系统整体结构
- `runtime-composition.md`
  解释运行时如何装配
- `request-lifecycle.md`
  解释一次请求如何穿过各层
- `../application/*.md`
  解释具体用例流程
