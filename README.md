# Galgame Character Skills

将长文本中的角色信息归纳为结构化摘要，并进一步生成技能包或适用于 SillyTavern 的角色卡。

这是一个基于 Flask 的分层应用，包含任务编排、checkpoint 恢复、VNDB 信息增强、工作区输出约定，以及一套按架构主题组织的文档树。

## 功能概览

给定一段文本（Galgame剧情脚本/小说/任何单个长文本文件），自动将其中一个角色蒸馏为skills或是适用于SillyTavern的角色卡。

支持使用VNDB相关信息进行信息增强。在提供VNDB信息时，生成角色卡将会自动使用对应的立绘合并一份.png角色卡。如果你的角色于VNDB的信息不全/有偏差，最好不要使用。切勿在使用非VN角色时使用，哪怕你的目标是具有视觉小说版本的同名角色。

最好自行对生成结果进行一定程度的调整或是检查，即使有VNDB提供的信息也不保证符合实际。尤其是那些不属于VN的角色。

只测试过几个Galgame剧情文本，一般来说不要把多路线的所有内容一股脑塞进来，是没问题的。

理论上来说你也可以使用QQ聊天记录，或是任何其他东西来生成。

支持一定程度上的读取被意外中断的单次任务并继续。

## 作者的话

请积极报告任何可能存在的问题。由于个人能力有限，一些东西可能没办法测试，缺少极长的剧本和各种边缘情况。出现任何问题请及时提交issue。切勿在出问题时重复点击各种按钮导致token被浪费掉。

QQ小团体 1021295370

如果你有任何改进或建议，欢迎提交Pull Request。但在提交之前：请确保你至少review并测试过一次你修改的内容。

## 演示视频

以下视频录制于较早版本，界面与实现细节可能已经变化，但可以作为能力演示参考：

- [将任意Galgame角色蒸馏为Skill](https://www.bilibili.com/video/av116387540374596/)
- [将任意Galgame角色转换为适配SillyTavern酒馆的角色卡](https://www.bilibili.com/video/av116392774933298/)

## 环境要求

- Python `>= 3.10`
- 建议使用虚拟环境

## 安装

推荐使用包安装方式：

```bash
pip install -e .
```

如果你只想按当前锁定依赖运行，也可以使用：

```bash
pip install -r requirements.txt
```

## 启动

```bash
python main.py
```

默认会启动本地 Web 服务，并尝试自动打开浏览器访问 `http://127.0.0.1:5000`。

## 配置方式

支持两类配置来源：

1. 在 Web 界面中直接填写
2. 通过项目根目录下的 `.env` 或环境变量提供默认值

如果你希望启动后自动带出默认配置，推荐使用仓库内的 `.env.example`：

```bash
cp .env.example .env
```

Windows PowerShell 可以使用：

```powershell
Copy-Item .env.example .env
```

然后按需修改 `.env` 中的内容。`.env` 已被 `.gitignore` 忽略，不会默认进入版本控制。

关于 `GCS_BASEURL`：

- 目前通常需要你自己确认目标服务是否要求带 `/v1`
- 如果服务端接口地址要求使用 `/v1`，请在 `GCS_BASEURL` 中手动写完整
- 例如 `https://api.openai.com/v1` 或 `http://localhost:11434/v1`
- 后续版本会优化这里的处理，尽量提供自动补全，或自动兼容“带 `/v1` / 不带 `/v1`”两种写法

支持的配置项如下：

- `GCS_BASEURL`
- `GCS_MODELNAME`
- `GCS_APIKEY`
- `GCS_MAX_RETRIES`
- `GCS_WORKSPACE_DIR`

`.env.example` 中包含以下配置项：

```env
GCS_BASEURL=https://api.openai.com/v1
GCS_MODELNAME=openai/gpt-4o-mini
GCS_APIKEY=your_api_key
GCS_MAX_RETRIES=3
GCS_WORKSPACE_DIR=workspace-data
```

说明：

- Web 界面中的填写值可以直接用于当前请求
- `.env` 和环境变量会作为默认值加载到页面
- `GCS_WORKSPACE_DIR` 为空时，工作区默认使用项目根目录
- `GCS_WORKSPACE_DIR` 为相对路径时，会基于项目根目录解析

## 基本使用流程

当前推荐流程分两步：

1. 先执行 `summarize`
   选择文本文件，填写角色名、补充说明、并发数、切片大小等参数，对角色进行归纳。
2. 再执行 `skills` 或 `chara_card`
   基于已经生成好的 summary 文件，为同一角色继续生成技能包或角色卡。

补充说明：

- `skills` 和 `chara_card` 都依赖已有的 summary 结果
- `POST /api/skills` 会根据 `mode` 分发到技能包或角色卡流程
- 长任务中断后可以从 checkpoint 列表中恢复

## 输入与输出目录

项目涉及两类路径约定：

### 输入文本

- Web 上传与文件扫描当前使用项目根目录下的 `resource/`
- 当前这版文档对应的实现里，`uploads/` 路径虽然已经出现在工作区路径约定中，但尚未接入输入主流程
- 因此在实际运行时，输入文件仍以 `resource/` 为准

### 工作区输出

以下目录由工作区规则管理；当 `GCS_WORKSPACE_DIR` 为空时，默认落在项目根目录下：

- `summaries/`：角色归纳结果
- `skills/`：技能包输出
- `cards/`：角色卡 JSON / PNG 输出
- `checkpoints/`：任务状态与恢复数据

如果你配置了 `GCS_WORKSPACE_DIR`，以上输出目录会切换到对应工作区根目录下。

## 文档索引

如果你想了解项目结构，从这里开始：

- [文档总索引](docs/README.md)
- [架构入口](docs/architecture.md)
- [架构总览](docs/architecture/overview.md)
- [运行时装配](docs/architecture/runtime-composition.md)
- [请求主链路](docs/architecture/request-lifecycle.md)
- [应用层说明](docs/application/README.md)
- [工作区说明](docs/workspace/README.md)
- [接口契约速查](docs/reference/api-contract.md)

## 开发与测试

运行测试：

```bash
pytest
```

项目当前已经按 `routes -> api -> application -> domain` 的主链路分层，并通过 `checkpoint / gateways / llm / files / workspace` 等支撑层协作。

## 使用建议

- 尽量清理文本中的引擎指令、明显无关的路线、无关角色主线和冲突内容
- 如果角色在文本里经常只以外号、代称或模糊称谓出现，最好通过补充说明显式告知模型
- 不建议把大量无关章节、结局分支或视角频繁切换的内容一次性全部塞进去
- 如果 VNDB 角色信息明显不完整或不准确，宁可不用，也不要强行增强

## 已知限制

- Gemini 系列模型可能仍然会受到安全策略影响，导致某些文本无法稳定处理
- 生成结果仍然需要人工检查，尤其是非 VN 角色或输入文本质量较差的情况
- 运行时长会受到模型速度、并发、文本长度、切片数和压缩策略影响

## 贡献

欢迎提交 issue 或 Pull Request。

如果你准备提交修改，请至少先完成一次自查和测试，避免把明显行为回归直接带进来。
