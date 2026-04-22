# VNDB 路由组

## 1. 范围

本组路由覆盖：

- `POST /api/vndb`

入口代码位于：

- `galgame_character_skills/routes/vndb.py`


## 2. 职责

这是一条单接口路由组，负责：

- 读取请求中的 `vndb_id`
- 调用 VNDB 查询逻辑
- 返回清洗后的角色信息


## 3. 当前结构

这组路由没有单独 facade，而是直接调用：

- `get_vndb_info_result(...)`
- `fetch_vndb_character(...)`

它同时依赖：

- `deps.r18_traits`
- `runtime.vndb_gateway`

这说明它是一个“轻查询 + 外部服务访问”的特殊接口组。


## 4. 设计特点

VNDB 查询在业务重要性上不如任务接口重，但又比本地纯查询多一层外部访问，因此结构上介于两者之间：

- 比 summary/config 查询更依赖运行时对象
- 比 tasks/checkpoints 更轻，不需要完整 facade


## 5. 后续约束

如果未来 VNDB 相关能力继续增长，例如：

- 多接口
- 缓存
- 复杂清洗策略
- 图像下载和补充数据同步

那么应考虑把它提升为更明确的 facade 或 application 用例，而不是继续堆在单个函数式入口里。
