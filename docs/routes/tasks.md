# Tasks 路由组

## 1. 范围

本组路由覆盖：

- `POST /api/summarize`
- `POST /api/skills`

入口代码位于：

- `galgame_character_skills/routes/tasks.py`


## 2. 角色

这是系统最核心的一组路由，因为它们承接：

- 文本归纳任务
- 技能包生成任务
- 角色卡生成任务

这里的路由函数本身很薄，但它们连接了整个请求主链路。


## 3. 调用方式

本组路由在注册时会先创建：

- `TaskApi(runtime)`

之后所有任务请求都会先进入 `TaskApi`，再由它转发到对应的 application service。

对应关系如下：

- `/api/summarize` -> `TaskApi.summarize(...)`
- `/api/skills` -> `TaskApi.dispatch_skills_mode(...)`


## 4. 为什么 `/api/skills` 既能生成技能又能生成角色卡

当前系统把两条生成任务统一放在：

- `/api/skills`

然后通过请求体中的：

- `mode`

决定实际执行：

- `skills`
- `chara_card`

这个设计的优点是入口少、前端调用简单；
代价是接口名和行为并不完全一一对应，因此文档必须把它讲清楚。


## 5. 依赖

本组路由只依赖：

- `runtime`
- `adapter`
- `TaskApi`

它不应直接依赖：

- checkpoint manager
- llm client
- file processor 的复杂组合逻辑


## 6. 设计评价

这组路由的结构是当前项目里最接近理想分层的一组：

- 路由薄
- facade 明确
- 下游进入 application
- 不直接拼装业务流程

因此它也适合作为后续新增任务型接口的参考模板。
