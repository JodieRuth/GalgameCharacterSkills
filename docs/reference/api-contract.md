# 接口契约速查

## 1. 通用返回格式

成功：

```json
{"success": true, "...": "..."}
```

失败：

```json
{"success": false, "message": "..."}
```


## 2. 主要接口

- `GET /api/files`
- `POST /api/files/upload`
- `POST /api/files/tokens`
- `POST /api/slice`
- `GET /api/config`
- `GET /api/summaries/roles`
- `POST /api/summaries/files`
- `POST /api/context-limit`
- `POST /api/vndb`
- `POST /api/summarize`
- `POST /api/skills`
- `GET /api/checkpoints`
- `GET /api/checkpoints/<id>`
- `DELETE /api/checkpoints/<id>`
- `POST /api/checkpoints/<id>/resume`


## 3. 任务接口关键字段

### summarize

- `role_name`
- `file_path` / `file_paths`
- `instruction`
- `output_language`
- `mode`
- `slice_size_k`
- `concurrency`
- `resume_checkpoint_id`

### skills

- `role_name`
- `mode=skills`
- `output_language`
- `compression_mode`
- `force_no_compression`
- `resume_checkpoint_id`

### chara_card

- `role_name`
- `mode=chara_card`
- `creator`
- `output_language`
- `compression_mode`
- `force_no_compression`
- `resume_checkpoint_id`
