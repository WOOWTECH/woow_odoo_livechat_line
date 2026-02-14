# LINE-Odoo 媒體傳輸調試發現

## 環境信息
- Odoo: woowodoomodule_odoo_1 (port 8069)
- Database: woowtech
- LINE Channel ID: 2009031005
- Webhook URL: http://woowtechaicoder-odootest.woowtech.io/line/webhook/1

## 調查發現

### 發現 1: [已確認] Webhook 正常工作
- 測試 webhook 成功創建 discuss.channel (id=33)
- 測試 webhook 成功創建 mail.message (id=2436, body="Test message")
- 簽名驗證正常工作

### 發現 2: [已確認] LINE OAuth 正常工作
- 成功獲取 access_token
- Token 有效期 2591999 秒

### 發現 3: [問題] 附件沒有被創建
- 數據庫中所有 LINE 訊息都沒有附件
- 圖片訊息的 body 是空的
- 表示 _download_line_content() 可能失敗或沒有被調用

### 發現 4: [已確認] LINE 圖片訊息正確收到
- message_id: 600969225636413827
- 類型: image
- 內容下載成功

### 發現 5: [根本原因] attachment_ids 過濾器問題
- Odoo 的 `message_post` 中 `attachment_ids` 參數有過濾器
- 過濾器要求 `res_model` 必須是 `mail.compose.message` 或 `mail.scheduled.message`
- 而且 `create_uid` 必須是當前用戶
- 我們創建的附件不符合這些條件，所以被過濾掉了

### 修復方案
- 改用 `attachments` 參數而不是 `attachment_ids`
- `attachments` 接受 `[(filename, content)]` 格式的元組列表
- 這樣可以繞過過濾器，讓 Odoo 自動創建並關聯附件

## 代碼審查

### webhook.py 流程
1. line_webhook() 接收請求
2. 驗證簽名
3. _handle_message_event() 處理訊息
4. _create_message() 創建 Odoo 訊息
5. _download_line_content() 下載媒體

### 潛在問題點
1. 簽名驗證可能失敗
2. LINE Content API 調用可能失敗
3. ir.attachment 創建可能失敗
4. message_post 可能沒有正確附加檔案
