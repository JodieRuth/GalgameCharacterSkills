# VNDB 接口编排

## 1. 入口文件

- `galgame_character_skills/api/vndb_api_service.py`
- `galgame_character_skills/api/vndb_service.py`


## 2. 结构分工

VNDB 相关接口被拆成两层：

### 2.1 `vndb_api_service.py`

负责：

- 从请求读取 `vndb_id`
- 做非空校验
- 把查询请求转发下去

### 2.2 `vndb_service.py`

负责：

- 规范化 VNDB ID
- 调用 `vndb_gateway`
- 处理响应状态码
- 清洗字段结构
- 过滤 R18 traits


## 3. 为什么拆成两层

这样拆分后：

- 接口层的参数校验和返回组织更清楚
- 真正的外部服务访问逻辑集中在 service 中
- 路由层不需要知道 VNDB ID 规范化等细节


## 4. 设计特点

VNDB 接口既不是纯本地查询，也不是长任务流程。

它处在一个中间位置：

- 有外部依赖访问
- 但没有 checkpoint
- 没有复杂 application workflow

因此它当前保留函数式 service 结构是可接受的。


## 5. 后续演进信号

如果 VNDB 相关能力继续增长到以下程度，就应考虑进一步上移到更明确的用例层：

- 多阶段同步
- 缓存与重试策略复杂化
- 图像下载与元数据合并
- 多个 VNDB 相关接口开始共享状态
