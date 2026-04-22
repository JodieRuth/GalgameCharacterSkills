# Summary Discovery

## 1. 核心文件

- `files/summary_discovery.py`


## 2. 职责

该模块负责在 summaries 工作区中发现：

- 有哪些角色已有产物
- 某个角色有哪些 summary 文件
- 某个角色的分析汇总文件在哪里


## 3. 当前实现方式

它通过遍历：

- 以 `_summaries` 结尾的目录

然后按文件名模式推断：

- markdown summary
- character card analysis json


## 4. 设计特点

这是一个典型的“基于目录命名约定”的发现模块。

它不依赖数据库或显式索引，而依赖：

- 工作区路径
- 文件命名规则

因此文档必须把目录约定讲清楚，否则会很难维护。
