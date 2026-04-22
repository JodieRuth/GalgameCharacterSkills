# 进度与切片结果

## 1. 进度更新

进度更新逻辑主要位于：

- `progress.py`

它负责：

- 更新 `current_step`
- 更新 `total_steps`
- 更新 `current_phase`
- 更新 `completed_items / failed_items / pending_items`
- 标记 `completed`
- 标记 `failed`


## 2. summarize 的切片语义

summarize 是对进度系统使用最深入的任务。

它会：

- 在开始时初始化 `pending_items`
- 在每个切片完成后调用 `mark_slice_completed(...)`
- 在全部完成或部分失败后更新状态

这让 summarize 的 checkpoint 既是“任务状态”，也是“切片执行进度表”。


## 3. `mark_slice_completed(...)`

这个方法的核心语义是原子地：

- 将当前切片加入 `completed_items`
- 从 `pending_items` 中移除
- 立即保存 checkpoint

这一步对恢复场景很关键，因为它直接决定：

- 断点恢复后哪些切片会被跳过


## 4. 切片结果持久化

切片结果相关逻辑位于：

- `slice_results.py`

它负责：

- 保存单片结果
- 读取单片结果

这与 `progress.py` 的区别是：

- `progress.py` 关心“状态”
- `slice_results.py` 关心“产物内容”


## 5. 进度与结果为什么要分开

因为“切片已完成”不等于“切片结果内容可用”，虽然它们通常同步发生。

拆分后带来的好处是：

- 进度语义更清晰
- 中间结果管理可以独立演进
- 列表查询时不需要加载全部切片内容


## 6. 设计评价

进度状态和切片结果分层管理，是当前 checkpoint 子系统比较成熟的一部分设计。
