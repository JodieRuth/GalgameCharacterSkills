# Checkpoints 路由组

## 1. 范围

本组路由覆盖：

- `GET /api/checkpoints`
- `GET /api/checkpoints/<checkpoint_id>`
- `DELETE /api/checkpoints/<checkpoint_id>`
- `POST /api/checkpoints/<checkpoint_id>/resume`

入口代码位于：

- `galgame_character_skills/routes/checkpoints.py`


## 2. 职责

这组路由负责：

- 查询任务列表
- 查询单个 checkpoint 详情
- 删除 checkpoint
- 触发恢复执行

它不负责 checkpoint 的具体存储实现，也不负责恢复后的业务逻辑本身。


## 3. facade 模式

本组路由采用和任务路由类似的 facade 模式：

- `CheckpointApi(runtime)`

这样路由层不需要了解：

- checkpoint 数据结构如何读取
- 恢复后如何按任务类型继续执行


## 4. 恢复请求的特殊性

`resume` 是本组里最特殊的接口，因为它不是单纯查询或删除。

处理链大致是：

`route -> CheckpointApi.resume_checkpoint -> ResumeTaskDispatcher -> TaskApi -> application service`

也就是说，这个接口本质上是“任务入口的另一种起点”。


## 5. query/path/body 的组合

本组接口同时覆盖了三类输入来源：

- query 参数：列表筛选使用
- path 参数：`checkpoint_id`
- body：恢复时的覆盖参数

因此这一组路由也比较适合用来说明为什么 routes 层仍然需要保留“读取入口参数”的职责。


## 6. 设计评价

这组路由的设计是健康的，主要优点是：

1. 路由薄
2. 恢复逻辑不直接暴露给 HTTP 入口
3. checkpoint 相关操作集中，边界清晰
