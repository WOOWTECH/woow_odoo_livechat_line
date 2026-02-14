# Odoo LINE 即時通訊整合

將 LINE Messaging API 與 Odoo 18 社群版 LiveChat 模組整合，實現 LINE 用戶與 Odoo 客服人員之間的雙向即時通訊。

[English](README.md)

## 功能特色

- **雙向訊息傳遞**：LINE 與 Odoo LiveChat 之間的訊息互通
- **多媒體支援**：
  - LINE 到 Odoo：圖片、影片、音訊、文件檔案
  - Odoo 到 LINE：圖片、影片、音訊、文件檔案（使用 Flex Message 卡片）
- **即時通訊**：透過 LINE webhook 即時傳遞訊息
- **訪客整合**：LINE 用戶以訪客身份顯示在 Odoo Discuss
- **客服回覆**：Odoo 客服人員可直接從 LiveChat 介面回覆

## 系統需求

- Odoo 18 社群版
- LINE Messaging API 頻道（LINE 官方帳號）
- HTTPS 端點（LINE 要求）

## 安裝方式

1. 將此模組複製到 Odoo 的 addons 目錄：
   ```bash
   git clone https://github.com/WOOWTECH/woow_odoo_livechat_line.git
   ```

2. 更新 Odoo 模組列表並安裝 `woow_odoo_livechat_line`

3. 在 LiveChat 設定中配置 LINE 頻道設定

## 設定方式

### LINE 開發者控制台

1. 在 [LINE Developers](https://developers.line.biz/) 建立 LINE Messaging API 頻道
2. 取得 **Channel ID** 和 **Channel Secret**
3. 設定 Webhook URL：`https://your-odoo-domain/line/webhook/<livechat_channel_id>`
4. 啟用 Webhook 並關閉自動回覆訊息

### Odoo 設定

1. 前往 **即時通訊 > 設定 > 頻道**
2. 編輯您的 LiveChat 頻道
3. 啟用 **LINE 整合**
4. 輸入 LINE **Channel ID** 和 **Channel Secret**
5. 儲存

## 訊息類型支援

| 類型 | LINE 到 Odoo | Odoo 到 LINE |
|------|-------------|-------------|
| 文字 | 支援 | 支援 |
| 圖片 | 支援 | 支援 |
| 影片 | 支援 | 支援 |
| 音訊 | 支援 | 支援 |
| 檔案/文件 | 支援 | 支援（Flex Message） |
| 貼圖 | 支援（轉為文字） | 不支援 |
| 位置 | 支援（轉為文字） | 不支援 |

## 架構說明

```
LINE 用戶                    Odoo
    |                          |
    |---- 訊息 --------------->| Webhook 控制器
    |                          |      |
    |                          |      v
    |                          | discuss.channel
    |                          |      |
    |                          |      v
    |                          | mail.message
    |                          |      |
    |<--- 回覆 ----------------|LINE API Mixin
    |                          |
```

## 檔案結構

```
woow_odoo_livechat_line/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── webhook.py          # LINE webhook 處理器
├── models/
│   ├── __init__.py
│   ├── discuss_channel.py  # 頻道與 LINE 用戶關聯
│   ├── im_livechat_channel.py  # LiveChat LINE 設定
│   ├── line_api.py         # LINE API 方法混入
│   └── mail_message.py     # 訊息鉤子處理 LINE 回覆
├── views/
│   └── im_livechat_channel_views.xml
├── security/
│   └── ir.model.access.csv
└── README.md
```

## 疑難排解

### 訊息未出現在 Odoo
- 檢查 LINE 開發者控制台中的 Webhook URL 是否正確設定
- 確認 HTTPS 憑證有效
- 檢查 Odoo 日誌中的 webhook 錯誤

### 媒體檔案無法傳輸
- 確保附件已生成 `access_token`
- 確認 HTTPS URL 可公開存取

### Flex Message 顯示為 JSON
- 這是舊版 LINE App 的已知限制
- 請更新 LINE App 到最新版本

## 授權

LGPL-3.0

## 作者

WOOWTECH

## 連結

- [GitHub 儲存庫](https://github.com/WOOWTECH/woow_odoo_livechat_line)
- [LINE Developers](https://developers.line.biz/)
- [LINE Messaging API 文件](https://developers.line.biz/en/docs/messaging-api/)
