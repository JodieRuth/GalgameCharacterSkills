# 任务请求模型

## 1. 核心文件

- `domain/task_requests.py`


## 2. 当前模型

当前定义了三类主要请求模型：

- `SummarizeRequest`
- `GenerateSkillsRequest`
- `GenerateCharacterCardRequest`

它们都继承：

- `BaseTaskRequest`


## 3. `BaseTaskRequest`

基础类的主要作用是：

- 统一 checkpoint 输入回填
- 统一导出可写入 checkpoint 的字段

这让请求模型不只是“HTTP 输入结构”，同时也是“恢复输入结构”。


## 4. 设计特点

这些请求模型有两个很重要的特点：

1. 负责从 payload 做第一层标准化
2. 明确声明哪些字段应该进入 checkpoint

这让恢复机制不必手写大量字段回填逻辑。


## 5. `model_name` 兼容

当前模型会兼容读取：

- `model_name`
- `modelname`

并统一内部字段名。

这是一个典型的“对外兼容，对内统一”的处理方式。
