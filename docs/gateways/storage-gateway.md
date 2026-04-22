# StorageGateway

## 1. 入口文件

- `galgame_character_skills/gateways/storage_gateway.py`


## 2. 职责

`StorageGateway` 封装文件系统常见操作：

- 路径存在性判断
- 创建目录
- 文本读写
- JSON 读写
- 删除文件
- 删除目录树
- 列出目录内容


## 3. 为什么需要它

application 层经常要做输出落盘，但不应该直接四处写：

- `open(...)`
- `os.makedirs(...)`
- `json.dump(...)`

通过 gateway 抽象后：

- 流程代码更聚焦业务语义
- 测试更容易替换文件系统操作


## 4. 默认实现

- `DefaultStorageGateway`

直接基于本地文件系统标准库实现。

这很符合当前项目作为本地工具的定位。
