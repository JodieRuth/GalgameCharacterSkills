# Gateways 层

## 1. 这一层负责什么

`gateways/` 定义 application 层依赖的基础设施能力边界。

当前主要包括：

- checkpoint
- storage
- llm
- tool
- vndb
- executor


## 2. 为什么需要 gateway

application 层需要使用很多外部能力，但它不应该知道：

- 这些能力的具体实现类
- 它们是否来自本地文件系统、HTTP、线程池或第三方 SDK

gateway 的作用就是：

- 用稳定接口隔离具体实现


## 3. 当前设计模式

每个 gateway 基本都采用：

- 一个抽象基类
- 一个 `Default*Gateway` 实现

这样在装配阶段可以使用默认实现，在测试或重构时也能替换。


## 4. 当前价值

gateway 是当前项目分层能够成立的重要支点：

1. application 不必直接实例化底层实现
2. 测试更容易注入 fake 或 stub
3. 具体实现变化更容易收敛到装配阶段


## 5. 当前需要继续注意的点

虽然 gateway 已经建立，但后续仍需持续防止：

- 新流程绕过 gateway 直接绑定具体实现

一旦这种情况增多，gateway 层就会失去意义。


## 6. 目录内文档

建议继续阅读：

- `checkpoint-gateway.md`
- `storage-gateway.md`
- `llm-gateway.md`
- `tool-gateway.md`
- `vndb-gateway.md`
- `executor-gateway.md`
