# TaskApi

## 1. 入口文件

- `galgame_character_skills/api/task_api.py`


## 2. 职责

`TaskApi` 是任务相关接口的 facade。

它负责：

- 暴露 summarize 入口
- 暴露技能生成入口
- 暴露角色卡生成入口
- 根据 `mode` 分发 `/api/skills` 请求


## 3. 为什么需要 facade

任务接口具有几个共性：

- 都依赖统一的 `runtime`
- 都会进入 application 层
- 都属于“长流程型接口”

把它们收敛到 `TaskApi` 的好处是：

- 路由层更薄
- 任务入口语义更集中
- 后续扩展新任务模式时更容易收口


## 4. 主要方法

### 4.1 `summarize(data)`

转发到：

- `run_summarize_task(...)`

### 4.2 `generate_skills_folder(data)`

转发到：

- `run_generate_skills_task(...)`

### 4.3 `generate_character_card(data)`

转发到：

- `run_generate_character_card_task(...)`

### 4.4 `dispatch_skills_mode(data)`

对 `/api/skills` 入口做模式分发：

- `mode == "chara_card"` -> 角色卡
- 其他情况 -> 技能生成

同时它还通过装饰器保证：

- `role_name` 非空


## 5. 设计评价

`TaskApi` 当前是一个边界比较清晰的 facade。

它的优点在于：

1. 不掺杂业务算法
2. 不直接接触 Flask
3. 与 routes 层配合自然
4. 与 application 层的职责边界明确


## 6. 后续演进方向

如果未来任务类型继续增加，可以继续沿用这个模式：

- 在 `TaskApi` 中增加稳定入口
- 在 application 层新增用例实现
- 不要让路由直接分发到底层流程
