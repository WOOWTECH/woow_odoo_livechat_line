# LINE-Odoo Debug Findings

## Architecture Overview

### Message Flow: LINE -> Odoo
```
LINE User -> LINE Server -> Webhook (/line/webhook/<channel_id>)
  -> _handle_message_event()
  -> _get_or_create_discuss_channel()
  -> _create_message()
  -> discuss_channel.message_post()
```

### Message Flow: Odoo -> LINE
```
Operator replies -> mail.message.create()
  -> _send_to_line_if_applicable()
  -> _notify_line_user()
  -> _line_push_message()
```

## Key Files
- `controllers/webhook.py` - LINE webhook 處理
- `models/mail_message.py` - 訊息攔截和轉發
- `models/discuss_channel.py` - LINE 通知發送
- `models/line_api.py` - LINE API 調用

## Findings

### Finding 1: [待調查]
訊息不即時出現 - 可能原因：
- message_post() 沒有觸發 bus 通知
- 使用了 sudo() 導致通知機制失效
- 前端 websocket 連接問題

### Finding 2: [待調查]
訊息遺漏 - 可能原因：
- webhook 簽名驗證失敗
- 異常處理吞掉了錯誤
- discuss channel 查找/創建失敗

## Investigation Notes

### 2024-02-14: Fixed Issues

1. **即時通知問題修復**
   - 移除了 `mail_create_nosubscribe=True`，這會阻止 bus 通知
   - 新增 `_broadcast()` 調用，通知操作員有新對話

2. **修改內容**
   - `controllers/webhook.py:276-292` - 移除 mail_create_nosubscribe，添加日誌
   - `controllers/webhook.py:217-219` - 添加 _broadcast() 通知操作員
