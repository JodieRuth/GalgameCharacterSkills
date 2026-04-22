# 配置与上下文查询接口

## 1. 入口文件

- `galgame_character_skills/api/config_api_service.py`
- `galgame_character_skills/api/context_api_service.py`


## 2. 职责

这一组接口负责：

- 返回脱敏后的运行配置
- 查询模型上下文窗口上限

它们属于最轻量的一类接口，没有任务流程，没有状态推进。


## 3. 配置接口

配置接口的重点不在于“读取配置”，而在于：

- 对敏感字段做脱敏
- 只暴露前端需要的配置视图

例如：

- `apikey` 不直接返回
- 改为 `has_apikey` 与 `apikey_masked`

这使得前端能知道配置状态，而不必接触真实密钥。


## 4. 上下文窗口接口

上下文接口只做一件事：

- 根据模型名调用 `get_model_context_limit(...)`

它的价值在于把“模型窗口大小”这个查询能力独立出来，让前端在任务开始前就能做判断或提示。


## 5. 设计评价

这两个接口的设计简单直接，适合作为函数式 `api service` 保持存在；
如果未来配置查询逻辑继续扩大，再考虑单独 facade 也不迟。
