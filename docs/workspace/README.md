# Workspace 支撑层

## 1. 这一层负责什么

`workspace/` 负责统一项目运行期目录定位规则。

它主要决定：

- 工作区根目录在哪里
- summaries / skills / cards / checkpoints 各自放在哪里


## 2. 为什么它重要

项目中很多模块都会读写磁盘，如果没有统一路径规则，就会很快出现：

- 各处自己拼路径
- 输出目录不一致
- 测试和运行环境切换困难


## 3. 核心模块

- `paths.py`


## 4. 目录内文档

建议继续阅读：

- `paths.md`
- `data-layout.md`
