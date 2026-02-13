# Odoo 18 LiveChat LINE 整合模組設計文件

## 概述

將 LINE Messaging API 整合到 Odoo 18 Community LiveChat，讓客服人員可以透過標準 Odoo Discuss 介面處理 LINE 用戶的訊息。

## 功能需求

- 在 LiveChat 頻道設定中新增 LINE 分頁，設定 Channel ID 和 Channel Secret
- LINE 用戶發起對話時，自動建立 Odoo LiveChat 對話
- 客服人員透過 Discuss 介面回覆 LINE 訊息
- 支援所有訊息類型（文字、圖片、影片、音訊、檔案、貼圖、位置）
- 同一 LINE 用戶再次發起對話時，進入同一對話頻道
- LINE 用戶預設以訪客方式處理，客服可手動關聯到 Odoo 聯絡人

---

## 架構設計

### 第一部分：資料模型

#### 1. 擴展 `im_livechat.channel` 模型

在 LiveChat 頻道設定表單新增 LINE 分頁：

| 欄位 | 類型 | 說明 |
|-----|------|-----|
| `line_enabled` | Boolean | 是否啟用 LINE 整合 |
| `line_channel_id` | Char | LINE Channel ID |
| `line_channel_secret` | Char | LINE Channel Secret（密碼類型） |
| `line_webhook_url` | Char (computed) | 自動產生的 Webhook URL |

#### 2. 擴展 `discuss.channel` 模型

儲存 LINE 對話關聯：

| 欄位 | 類型 | 說明 |
|-----|------|-----|
| `line_user_id` | Char | LINE User ID |
| `line_display_name` | Char | LINE 顯示名稱 |
| `line_picture_url` | Char | LINE 大頭貼 URL |

#### 3. 擴展 `mail.guest` 模型

讓訪客可關聯 LINE 資訊與 Partner：

| 欄位 | 類型 | 說明 |
|-----|------|-----|
| `line_user_id` | Char | LINE User ID |

客服可透過介面將 `mail.guest` 關聯到 `res.partner`。

---

### 第二部分：Webhook 與訊息流程

#### 1. Webhook Controller

建立 `/line/webhook/<channel_id>` 端點：
- 驗證 LINE 簽章（使用 Channel Secret）
- 接收 LINE 事件（message、follow、unfollow）
- 處理各種訊息類型

#### 2. 訊息接收流程（LINE → Odoo）

```
LINE 用戶發送訊息
    ↓
LINE Platform 呼叫 Webhook
    ↓
驗證簽章
    ↓
查找或建立 mail.guest（透過 line_user_id）
    ↓
查找或建立 discuss.channel（訪客對話頻道）
    ↓
建立 mail.message（訊息記錄）
    ↓
客服人員在 Discuss 看到新訊息
```

#### 3. 訊息回覆流程（Odoo → LINE）

```
客服人員在 Discuss 回覆訊息
    ↓
Override mail.message 的 create 方法
    ↓
偵測是否為 LINE 對話頻道
    ↓
呼叫 LINE Messaging API 發送訊息
    ↓
LINE 用戶收到回覆
```

---

### 第三部分：訊息類型處理

#### LINE → Odoo 訊息類型對應

| LINE 類型 | Odoo 處理方式 |
|----------|--------------|
| 文字 (text) | 直接存為 mail.message body |
| 圖片 (image) | 下載後存為 ir.attachment，顯示在訊息中 |
| 影片 (video) | 下載後存為 ir.attachment |
| 音訊 (audio) | 下載後存為 ir.attachment |
| 檔案 (file) | 下載後存為 ir.attachment |
| 貼圖 (sticker) | 顯示為圖片（使用 LINE 貼圖 URL）|
| 位置 (location) | 顯示為文字（地址 + Google Maps 連結）|

#### Odoo → LINE 訊息類型對應

| Odoo 操作 | LINE 發送方式 |
|----------|--------------|
| 純文字訊息 | text message |
| 附帶附件 | 依附件類型發送（image/video/audio/file）|

附件與檔案處理跟隨 Odoo LiveChat 原生方式。

---

### 第四部分：前端介面

#### 1. LiveChat 頻道設定表單 - LINE 分頁

在 `im_livechat.channel` 表單新增 "LINE" 分頁：

```
┌─────────────────────────────────────────────────┐
│ [Operators] [Options] [Channel Rules] [Widget] [LINE] │
├─────────────────────────────────────────────────┤
│                                                 │
│  ☑ 啟用 LINE 整合                               │
│                                                 │
│  Channel ID:    [________________]              │
│  Channel Secret: [________________]             │
│                                                 │
│  Webhook URL:   https://your-odoo.com/line/     │
│                 webhook/1  [複製]               │
│                                                 │
└─────────────────────────────────────────────────┘
```

#### 2. Discuss 對話介面 - 關聯聯絡人

在 LINE 訪客對話中，客服人員可以：
- 看到 LINE 用戶的顯示名稱和大頭貼
- 透過按鈕或選單將訪客關聯到現有 `res.partner`

---

### 第五部分：模組結構

**模組名稱：** `woow_odoo_livechat_line`

```
woow_odoo_livechat_line/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── webhook.py          # LINE Webhook 端點
├── models/
│   ├── __init__.py
│   ├── im_livechat_channel.py  # 擴展 LiveChat 頻道
│   ├── discuss_channel.py      # 擴展 Discuss 頻道
│   └── mail_guest.py           # 擴展訪客模型
├── views/
│   └── im_livechat_channel_views.xml  # LINE 分頁表單
├── security/
│   └── ir.model.access.csv
└── static/
    └── src/
        └── js/                 # 前端擴展（如需要）
```

**相依模組：**
- `im_livechat`
- `mail`

---

### 第六部分：安全與錯誤處理

#### 1. 安全性

- Webhook 簽章驗證（使用 LINE Channel Secret 驗證 X-Line-Signature）
- Channel Secret 欄位使用密碼類型儲存
- Webhook URL 僅接受 POST 請求

#### 2. 錯誤處理

- LINE API 呼叫失敗時記錄 log，不中斷對話流程
- Webhook 處理失敗時回傳 200（避免 LINE 重試轟炸）
- 媒體下載失敗時顯示提示訊息

---

## 實作優先順序

1. 基礎模組結構與資料模型
2. LiveChat 頻道設定介面（LINE 分頁）
3. Webhook 端點與簽章驗證
4. 訊息接收流程（LINE → Odoo）
5. 訊息回覆流程（Odoo → LINE）
6. 訪客關聯聯絡人功能
7. 多媒體訊息支援
