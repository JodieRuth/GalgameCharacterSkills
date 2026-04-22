# VndbGateway

## 1. 入口文件

- `galgame_character_skills/gateways/vndb_gateway.py`


## 2. 职责

`VndbGateway` 负责抽象对 VNDB HTTP 接口的访问。

当前核心能力只有一个：

- 查询角色信息


## 3. 为什么值得单独抽象

尽管当前功能很小，但它已经涉及：

- 外部 HTTP 请求
- 超时处理
- 固定 endpoint

抽成 gateway 后，业务层只需关心：

- 给我角色数据

而不需要知道请求是如何发出的。


## 4. 默认实现

默认实现基于：

- `requests.post(...)`

并封装了：

- endpoint
- timeout
- 超时异常转义
