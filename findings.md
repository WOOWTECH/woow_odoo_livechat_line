# Findings - Odoo 18 LiveChat LINE 整合

## LINE Messaging API 資訊
- Channel ID 和 Channel Secret 用於驗證
- Access Token 透過 API 動態取得
- Webhook 簽章使用 HMAC-SHA256 驗證

## Odoo 18 LiveChat 相關模型
- `im_livechat.channel` - LiveChat 頻道設定
- `discuss.channel` - 對話頻道
- `mail.guest` - 訪客模型
- `mail.message` - 訊息記錄

## 訊息類型對應
| LINE 類型 | Odoo 處理 |
|----------|----------|
| text | mail.message body |
| image | ir.attachment |
| video | ir.attachment |
| audio | ir.attachment |
| file | ir.attachment |
| sticker | 圖片顯示 |
| location | 文字 + Google Maps 連結 |
