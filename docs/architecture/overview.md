# 架构总览

## 1. 项目目标

`GalgameCharacterSkills` 是一个本地运行的 Flask 工具，围绕“从文本到角色产物”的处理链提供以下核心能力：

- 扫描和上传资源文本
- 对文本进行切片和角色归纳
- 基于归纳结果生成技能包
- 基于分析结果生成角色卡 JSON/PNG
- 提供 checkpoint 持久化、失败恢复和任务列表管理


## 2. 系统视角

从系统视角看，项目可以拆成四条主线：

1. HTTP 请求入口
2. 任务编排与业务流程
3. 基础设施抽象与外部依赖访问
4. 工作区数据与 checkpoint 持久化

一次典型请求的流向是：

`routes -> api -> application -> gateways / files / checkpoint / llm / workspace`


## 3. 顶层分层

当前代码主要由以下层次构成：

- `routes/`
  HTTP 路由注册层，负责 URL 分组和请求入口
- `api/`
  接口编排层，负责参数读取、任务分发和结果组装
- `application/`
  用例层，负责 summarize / skills / character-card 等核心流程
- `domain/`
  稳定的数据契约和任务类型定义
- `gateways/`
  对 checkpoint、LLM、工具、存储、执行器、VNDB 等基础设施的抽象边界
- `checkpoint/`
  checkpoint 的存储、查询、进度、恢复与中间结果管理
- `llm/`
  模型交互能力、prompt 构造、消息流和 provider 适配
- `files/`
  文件扫描、切片与 summary 发现
- `workspace/`
  工作区路径和输出目录约定
- `web/`
  前端模板和静态页面入口


## 4. 关键入口

系统的主要入口点包括：

- `main.py`
  本地启动 Flask 服务并打开浏览器
- `galgame_character_skills/app.py`
  创建应用、注册路由、装配运行时依赖
- `galgame_character_skills/application/app_container.py`
  构建应用级依赖和任务运行时依赖


## 5. 核心业务流程

当前最重要的三条业务流程是：

### 5.1 summarize

处理链：

1. 接收文本文件路径
2. 执行切片
3. 调用 LLM 逐片归纳
4. 保存切片结果
5. 更新 checkpoint 进度
6. 汇总返回任务结果

### 5.2 generate_skills

处理链：

1. 查找角色 summary 文件
2. 构建技能生成上下文
3. 初始化 LLM tool loop
4. 生成技能产物
5. 写入技能目录并完成任务收尾

### 5.3 generate_chara_card

处理链：

1. 读取分析结果
2. 根据需要压缩分析上下文
3. 进入角色卡字段写入流程
4. 生成 JSON
5. 如有图片则生成 PNG
6. 更新 checkpoint 状态并返回结果


## 6. 横切能力

系统中有几个横切子系统会影响多条流程：

- checkpoint
  负责任务状态、LLM 会话状态和切片结果持久化
- gateways
  负责把 application 层与具体实现解耦
- llm
  负责请求发送、tool loop 支撑、prompt 和 provider 配置
- workspace
  负责 summaries、skills、cards、checkpoints 等目录路径约定


## 7. 当前架构判断

当前项目总体上已经具备明确的分层意图，尤其在以下方面较清晰：

- `routes -> api -> application` 的主链路基本成型
- `application/shared` 已抽出一部分横切流程
- `gateways/` 已经建立起基础设施抽象边界
- checkpoint 已经被独立为单独子系统

但当前仍存在一些需要继续收敛的地方：

- 文档结构落后于实际代码结构
- 部分查询型接口仍保留不同风格的组织方式
- 个别流程的层次边界还需要持续统一


## 8. 建议阅读路径

如果要继续理解这个系统，建议下一步阅读：

1. `dependency-rules.md`
2. `runtime-composition.md`
3. `request-lifecycle.md`
4. `../application/README.md`
5. `../checkpoint/README.md`


## 9. 本文档的边界

本文档只回答：

- 系统由哪些层组成
- 各层大致职责是什么
- 系统的主要处理链是什么

本文档不展开：

- 每个目录的详细文件职责
- 各接口的请求/响应字段
- checkpoint 的具体数据结构
- LLM prompt 和 tool loop 的细节

这些内容应在各自专题文档中单独维护。
