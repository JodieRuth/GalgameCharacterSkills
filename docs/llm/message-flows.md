# Message Flow

## 1. 核心文件

- `llm/message_flows.py`


## 2. 职责

message flow 负责把：

- prompt builder
- 输入文本
- 角色信息
- 输出路径

组装成最终的：

- `messages`
- `tools`


## 3. 当前主要 flow

当前包含的代表性 flow：

- summarize 内容发送
- summarize 角色卡分析发送
- skills 初始化消息构造
- compression 消息构造


## 4. 为什么它很重要

它是 `prompt` 和 `application` 之间的过渡层。

如果没有这层，application 需要自己关心：

- prompt 组合
- messages 结构
- tools 结构

那样业务代码会迅速失去可读性。
