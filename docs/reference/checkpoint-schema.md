# Checkpoint 结构速查

## 1. 顶层字段

- `checkpoint_id`
- `task_type`
- `status`
- `created_at`
- `updated_at`
- `input_params`
- `progress`
- `intermediate_results`
- `llm_conversation_state`
- `metadata`


## 2. `progress`

- `current_step`
- `total_steps`
- `current_phase`
- `completed_items`
- `failed_items`
- `pending_items`
- `error_message`


## 3. `llm_conversation_state`

- `messages`
- `tool_call_history`
- `last_response`
- `iteration_count`
- `all_results`
- `fields_data`
