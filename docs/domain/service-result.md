# 统一结果结构

## 1. 核心文件

- `domain/service_result.py`


## 2. 目标

该模块为整个系统提供统一的结果风格：

- `success`
- `message`
- `payload`


## 3. `ServiceResult`

`ServiceResult` 是一个轻量 dataclass，它可以把：

- 成功标记
- 消息
- 额外字段

转换为标准 `dict` 结果。


## 4. 为什么它重要

当前项目中，路由、API、application 的返回最终都要汇聚成 JSON。

统一结果结构的好处是：

- 接口风格更一致
- 失败处理更统一
- 前端可以稳定依赖 `success` 和 `message`
