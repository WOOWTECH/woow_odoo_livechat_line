# PRD: LINE-Odoo 媒體傳輸調試

## 目標
修復 LINE ↔ Odoo LiveChat 之間的檔案、圖片、音訊傳輸功能

## 當前狀態
- 文字訊息：未確認是否正常
- 圖片傳輸：LINE → Odoo 失敗
- 檔案傳輸：LINE → Odoo 失敗
- 音訊傳輸：LINE → Odoo 失敗

## 調試階段

### Phase 1: 確認 Webhook 接收 [pending]
- [ ] 確認 LINE webhook URL 設定正確
- [ ] 確認 Odoo 日誌有收到 webhook 請求
- [ ] 確認簽名驗證通過

### Phase 2: 確認訊息處理 [pending]
- [ ] 確認 message_type 正確識別 (image/video/audio/file)
- [ ] 確認 message_id 正確取得
- [ ] 確認進入 _download_line_content 流程

### Phase 3: 確認 LINE API 調用 [pending]
- [ ] 確認 access_token 取得成功
- [ ] 確認 Content API URL 正確
- [ ] 確認 API 回應狀態碼
- [ ] 確認下載的內容大小

### Phase 4: 確認附件創建 [pending]
- [ ] 確認 ir.attachment 創建成功
- [ ] 確認 message_post 包含 attachment_ids
- [ ] 確認訊息在 Odoo 中顯示

## 技術細節

### LINE Content API
```
URL: https://api-data.line.me/v2/bot/message/{messageId}/content
Headers: Authorization: Bearer {accessToken}
Response: Binary content with Content-Type header
```

### 關鍵文件
- controllers/webhook.py - Webhook 處理
- models/line_api.py - LINE API 調用
- models/im_livechat_channel.py - LINE 配置

## 錯誤日誌
| 時間 | 錯誤 | 嘗試 | 結果 |
|------|------|------|------|
| | | | |

## 測試計劃
1. 發送 LINE 訊息，檢查 webhook 日誌
2. 發送 LINE 圖片，檢查下載流程
3. 確認 Odoo 中顯示結果
