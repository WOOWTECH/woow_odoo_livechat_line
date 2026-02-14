# LINE-Odoo LiveChat Debug Plan

## Goal
調試並修復 LINE 到 Odoo LiveChat 的雙向對話功能

## Current Issues
1. **訊息延遲** - LINE 訊息不會即時出現在 Odoo，需要重新載入頁面
2. **訊息遺漏** - 部分訊息沒有傳到 Odoo

## Phases

### Phase 1: 檢查 Webhook 接收 [in_progress]
- [ ] 確認 LINE webhook 是否正確接收訊息
- [ ] 檢查 Odoo 日誌中的 webhook 請求
- [ ] 驗證簽名驗證是否正確

### Phase 2: 檢查訊息創建 [pending]
- [ ] 確認 `message_post()` 是否正確執行
- [ ] 檢查 discuss channel 是否正確創建/找到
- [ ] 驗證 guest 用戶是否正確關聯

### Phase 3: 檢查即時通知 [pending]
- [ ] 確認 Odoo bus/websocket 是否推送訊息通知
- [ ] 檢查 `message_post()` 是否觸發正確的通知
- [ ] 測試前端是否接收到 bus 通知

### Phase 4: 檢查 Odoo 到 LINE 回覆 [pending]
- [ ] 確認客服回覆是否觸發 LINE push message
- [ ] 檢查 `from_line_webhook` 上下文標記是否正確防止回環
- [ ] 驗證 LINE API 推送是否成功

### Phase 5: 整體測試 [pending]
- [ ] 從 LINE 發送文字訊息
- [ ] 從 Odoo 回覆
- [ ] 確認雙向即時通訊

## Test Plan
1. 從 LINE 發送 "Test 1" 訊息
2. 檢查 Odoo 日誌確認 webhook 接收
3. 檢查 Odoo Discuss 是否顯示訊息
4. 從 Odoo 回覆 "Reply 1"
5. 確認 LINE 收到回覆

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| | | |

## Files Modified
- controllers/webhook.py
- models/mail_message.py
- models/im_livechat_channel.py
