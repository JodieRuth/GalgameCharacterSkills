# 文件接口编排

## 1. 入口文件

- `galgame_character_skills/api/file_api_service.py`


## 2. 职责

这个模块提供文件相关的薄编排函数：

- 扫描文件
- 上传文件
- token 估算
- 切片预估

它们大多围绕：

- `FileProcessor`

做轻量封装。


## 3. 设计特点

这一组函数的共同特征是：

- 不进入 application 层
- 不依赖 checkpoint
- 以轻量查询/准备接口为主

因此它们保留在函数式 service 形态是合理的。


## 4. 参数校验

这里使用了两种装饰器：

- `require_non_empty_field(...)`
- `require_condition(...)`

典型用途包括：

- 校验 `file_path`
- 校验是否选择了文件列表


## 5. 结果风格

文件接口统一返回：

- `ok_result(...)`
- `fail_result(...)`

这意味着即使不进入 application 层，接口风格依旧和任务型请求保持一致。


## 6. 边界判断

如果文件接口后续开始涉及：

- 长流程状态
- checkpoint
- 多阶段任务恢复

那么它们就不再适合继续停留在这里，而应提升到 application 层。
