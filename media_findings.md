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

### 發現 4: [待調查]
需要確認實際 LINE 圖片訊息的 webhook payload 和 message_id

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
