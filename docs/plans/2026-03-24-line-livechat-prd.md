# PRD: Odoo LINE LiveChat Integration

# PRD: Odoo LINE LiveChat 即時通訊整合

---

## 1. Overview / 概述

**Module:** `woow_odoo_livechat_line`
**Version:** 18.0.1.0.0
**Author:** WoowTech
**License:** LGPL-3
**Dependencies:** `im_livechat`, `mail`

This module bridges LINE Messaging API with Odoo 18 LiveChat, enabling customer service operators to handle LINE conversations directly within Odoo Discuss. LINE users are automatically identified by their profile, linked to Odoo contacts (`res.partner`), and assigned persistent conversation channels.

本模組將 LINE Messaging API 與 Odoo 18 LiveChat 串接，讓客服人員可以直接在 Odoo Discuss 介面中處理 LINE 對話。LINE 用戶會自動透過 Profile API 辨識身份，與 Odoo 聯絡人（`res.partner`）綁定，並分配持久化的對話頻道。

---

## 2. Problem Statement / 問題描述

**EN:** Businesses using Odoo as their CRM/ERP need to communicate with customers on LINE (dominant messaging platform in Taiwan, Japan, Thailand). Without integration, operators must switch between Odoo and LINE Official Account, losing conversation context and customer data linkage.

**中文：** 使用 Odoo 作為 CRM/ERP 的企業需要透過 LINE（台灣、日本、泰國的主流通訊平台）與客戶溝通。若無整合，客服人員必須在 Odoo 和 LINE 官方帳號之間切換，失去對話脈絡和客戶資料的關聯性。

---

## 3. Goals & Success Criteria / 目標與成功標準

| Goal / 目標 | Criteria / 標準 | Status / 狀態 |
|---|---|---|
| Bidirectional messaging / 雙向訊息 | LINE <-> Odoo text, image, video, audio, file, sticker, location | Done |
| User identification / 用戶辨識 | LINE displayName shown in Discuss (not generic "LINE User") | Done |
| Auto partner creation / 自動建立聯絡人 | `res.partner` auto-created with `line_user_id` on first message | Done |
| Contact binding / 聯絡人綁定 | `line_user_id` stored on `res.partner` with unique constraint | Done |
| No duplicates / 無重複 | Same LINE user = 1 guest + 1 partner + 1 channel per livechat | Done |
| Performance / 效能 | Profile API only called when needed (new user or missing data) | Done |

---

## 4. Architecture / 架構

### 4.1 System Diagram / 系統架構圖

```
LINE User
    |
    | (HTTPS webhook)
    v
[LINE Platform] --> [Cloudflare Tunnel] --> [Odoo 18]
                                                |
                                    +-----------+-----------+
                                    |           |           |
                                Webhook    LINE API    Odoo ORM
                               Controller   Mixin      Models
                                    |           |           |
                                    v           v           v
                               Signature   Token Cache  mail.guest
                               Verify      Profile API  res.partner
                               Event       Push API     discuss.channel
                               Dispatch    Content DL   mail.message
```

### 4.2 Data Flow: LINE -> Odoo / 資料流：LINE 到 Odoo

```
1. LINE webhook POST /line/webhook/<channel_id>
2. HMAC-SHA256 signature verification
3. Event dispatch (message / follow / unfollow)
4. _get_or_create_guest()
   a. Search mail.guest by line_user_id
   b. If new: fetch LINE Profile API -> get displayName
   c. _get_or_create_line_partner() -> search/create res.partner
   d. Create mail.guest with line_partner_id linked
   e. If existing with generic name: update name from profile
   f. If existing without partner: create and link partner
5. _get_or_create_discuss_channel()
   a. Search by (line_user_id, livechat_channel_id)
   b. If new: create channel, assign operator, add guest member
   c. If existing: update line_display_name + anonymous_name
6. _create_message()
   a. Parse message type (text/image/video/audio/file/sticker/location)
   b. Download media content if applicable
   c. message_post() with author_guest_id and context flag
```

### 4.3 Data Flow: Odoo -> LINE / 資料流：Odoo 到 LINE

```
1. Operator posts message in Discuss channel
2. mail.message.create() override intercepts
3. Skip if context has from_line_webhook=True (prevent loop)
4. Check if channel has line_user_id (is LINE conversation)
5. discuss_channel._notify_line_user(message)
   a. Get access token (cached, 30-day validity)
   b. Build message objects (text, image, video, audio, flex file card)
   c. Generate attachment access tokens for media URLs
   d. Ensure HTTPS URLs (LINE API requirement)
   e. Push via LINE Push Message API (batch max 5 per request)
```

---

## 5. Data Model / 資料模型

### 5.1 Model Extensions / 模型擴展

#### `res.partner` (New Extension / 新增擴展)

| Field | Type | Attributes | Description / 描述 |
|---|---|---|---|
| `line_user_id` | Char | indexed, unique, copy=False | LINE User ID for this contact / 聯絡人的 LINE User ID |

SQL Constraint: `unique(line_user_id)` - prevents duplicate LINE bindings.

#### `mail.guest` (Extended / 擴展)

| Field | Type | Attributes | Description / 描述 |
|---|---|---|---|
| `line_user_id` | Char | indexed, unique | LINE User ID / LINE 用戶唯一識別碼 |
| `line_partner_id` | Many2one -> res.partner | | Linked contact / 綁定的聯絡人 |

SQL Constraint: `unique(line_user_id)` - prevents duplicate guests.

#### `discuss.channel` (Extended / 擴展)

| Field | Type | Attributes | Description / 描述 |
|---|---|---|---|
| `line_user_id` | Char | indexed | LINE User ID for this conversation / 對話的 LINE 用戶 |
| `line_display_name` | Char | | Cached LINE display name / 快取的 LINE 顯示名稱 |
| `line_picture_url` | Char | | Cached profile picture URL / 快取的大頭貼網址 |

#### `im_livechat.channel` (Extended / 擴展)

| Field | Type | Attributes | Description / 描述 |
|---|---|---|---|
| `line_enabled` | Boolean | default=False | Enable LINE integration / 啟用 LINE 整合 |
| `line_channel_id` | Char | required when enabled | LINE Channel ID / LINE 頻道 ID |
| `line_channel_secret` | Char | password, required when enabled | LINE Channel Secret / LINE 頻道密鑰 |
| `line_webhook_url` | Char | computed | Auto-generated webhook URL / 自動產生的 webhook 網址 |

### 5.2 Entity Relationships / 實體關係

```
im_livechat.channel (LINE config)
    |
    | 1:N
    v
discuss.channel (per LINE user per livechat channel)
    |
    | N:1              N:1
    v                  v
mail.guest -------> res.partner
 (line_user_id)     (line_user_id)
 (line_partner_id)
```

---

## 6. API Integration / API 整合

### 6.1 LINE Messaging API Endpoints Used

| Endpoint | Method | Purpose / 用途 |
|---|---|---|
| `/v2/oauth/accessToken` | POST | Get access token (cached 30 days) / 取得存取權杖 |
| `/v2/bot/profile/{userId}` | GET | Fetch user displayName / 取得用戶顯示名稱 |
| `/v2/bot/message/push` | POST | Send message to user / 推送訊息給用戶 |
| `/v2/bot/message/{messageId}/content` | GET | Download media content / 下載媒體內容 |

### 6.2 Webhook Endpoint

```
POST /line/webhook/<int:channel_id>
Auth: public (no Odoo session required)
CSRF: disabled
Security: HMAC-SHA256 signature verification
```

### 6.3 Token Caching Strategy / 權杖快取策略

- In-memory dict: `{channel_id: {token, expires_at}}`
- LINE tokens valid for 30 days (2,592,000 seconds)
- Refreshed 5 minutes before expiry (`TOKEN_EXPIRY_BUFFER = 300`)
- No database storage (reset on Odoo restart, auto-refreshed on next call)

---

## 7. Supported Message Types / 支援的訊息類型

### 7.1 LINE -> Odoo (Inbound / 入站)

| LINE Type | Odoo Representation / Odoo 呈現方式 |
|---|---|
| Text | Plain text message body |
| Image | Downloaded JPEG attachment |
| Video | Downloaded MP4 attachment + `[Video]` label |
| Audio | Downloaded M4A attachment + `[Audio]` label |
| File | Downloaded file attachment (original filename) |
| Sticker | `[Sticker: packageId/stickerId]` text |
| Location | Google Maps link with title and address |

### 7.2 Odoo -> LINE (Outbound / 出站)

| Odoo Content | LINE Type / LINE 訊息類型 |
|---|---|
| Text (HTML stripped) | Text message |
| Image attachment | Image message (HTTPS URL) |
| Video attachment | Video message (HTTPS URL + preview) |
| Audio attachment | Audio message (HTTPS URL + duration) |
| Other file attachment | Flex Message file card (extension badge + download link) |

---

## 8. User Identification Flow / 用戶辨識流程

### 8.1 New LINE User (First Message) / 新用戶（首次訊息）

```
1. Webhook receives message with line_user_id
2. Search mail.guest -> not found
3. Call LINE Profile API -> get displayName (e.g. "孟緯 Elmo")
4. Search res.partner by line_user_id -> not found
5. Create res.partner (name="孟緯 Elmo", line_user_id="U545c1c2...")
6. Create mail.guest (name="孟緯 Elmo", line_user_id, line_partner_id)
7. Create discuss.channel (line_display_name="孟緯 Elmo")
```

### 8.2 Returning User (Subsequent Messages) / 回訪用戶

```
1. Search mail.guest -> found, has name + partner
2. Skip Profile API call (performance optimization)
3. Reuse existing discuss.channel
```

### 8.3 Legacy User Upgrade (Existing Guest Without Partner) / 舊用戶升級

```
1. Search mail.guest -> found, name="LINE User", no partner
2. Call LINE Profile API -> get displayName
3. Update guest name: "LINE User" -> "孟緯 Elmo"
4. Create res.partner and link to guest
5. Update channel display_name + anonymous_name
```

### 8.4 Manual Partner Linking (Wizard) / 手動綁定（精靈）

```
1. Operator opens guest -> "Link to Contact"
2. Wizard shows partner search (no create in wizard)
3. Select existing partner -> Link
4. Updates: guest.line_partner_id, guest.name = partner.name
5. Syncs: partner.line_user_id = guest.line_user_id
```

---

## 9. Security / 安全性

| Concern / 安全考量 | Implementation / 實作方式 |
|---|---|
| Webhook authentication | HMAC-SHA256 signature verification (constant-time comparison) |
| XSS prevention | `markupsafe.escape()` for user-provided content (location) |
| CSRF | Disabled for webhook (LINE cannot send CSRF tokens) |
| Access control | Webhook runs as `auth='public'`, all ORM calls use `sudo()` |
| URL security | Attachment access tokens generated for media URLs |
| HTTPS enforcement | All media URLs converted to HTTPS before sending to LINE |
| Data uniqueness | SQL unique constraints on `line_user_id` (partner + guest) |
| Wizard access | Only `im_livechat_group_user` can access linking wizard |

---

## 10. File Structure / 檔案結構

```
woow_odoo_livechat_line/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── webhook.py              # Webhook controller + user identification
├── models/
│   ├── __init__.py
│   ├── line_api.py             # LINE API mixin (token, push, profile, content)
│   ├── im_livechat_channel.py  # LiveChat channel LINE config
│   ├── discuss_channel.py      # Channel extension + outbound messaging
│   ├── mail_guest.py           # Guest extension (line_user_id, line_partner_id)
│   ├── mail_message.py         # Message hook (operator reply -> LINE push)
│   └── res_partner.py          # Partner extension (line_user_id)
├── views/
│   ├── im_livechat_channel_views.xml  # LINE tab in LiveChat config
│   └── res_partner_views.xml          # LINE ID field in contact form
├── wizard/
│   ├── __init__.py
│   ├── line_guest_link_partner_wizard.py       # Manual partner linking
│   └── line_guest_link_partner_wizard_views.xml
├── security/
│   └── ir.model.access.csv     # ACL for wizard model
└── docs/
    └── plans/
```

---

## 11. Configuration / 設定方式

### 11.1 Odoo Side / Odoo 端

1. Install module `woow_odoo_livechat_line`
2. Go to **LiveChat > Channels** > select or create a channel
3. Open **LINE** tab
4. Check **Enable LINE Integration**
5. Enter **LINE Channel ID** and **LINE Channel Secret**
6. Copy the auto-generated **Webhook URL**

### 11.2 LINE Developers Console / LINE 開發者控制台

1. Create a **Messaging API** channel
2. Set **Webhook URL** to the copied URL from Odoo
3. Enable **Use webhook**
4. Disable **Auto-reply messages** and **Greeting messages**
5. Note the **Channel ID** and **Channel Secret**

---

## 12. Deployment / 部署

### 12.1 Test Environment / 測試環境

| Item | Value |
|---|---|
| External URL | https://odoo-linelivechat.woowtech.io |
| Local URL | http://localhost:9072 |
| Credentials | admin / admin |
| Database | odoolinelivechat |
| LINE Channel ID | 2009031005 |
| Webhook URL | https://odoo-linelivechat.woowtech.io/line/webhook/1 |
| Containers | odoo-linelivechat-web (Odoo 18, port 9072), odoo-linelivechat-db (PostgreSQL 16), odoo-linelivechat-tunnel (Cloudflare) |
| Addons Path | `/mnt/extra-addons/woow_odoo_livechat_line/` (container) |

### 12.2 Deployment Steps / 部署步驟

```bash
# 1. Sync module files
rsync -av woow_odoo_livechat_line/ <addons_path>/woow_odoo_livechat_line/

# 2. Upgrade module
odoo -c /etc/odoo/odoo.conf -d <dbname> -u woow_odoo_livechat_line --stop-after-init --no-http

# 3. Restart Odoo
podman restart odoo-linelivechat-web
```

---

## 13. Future Roadmap / 未來規劃

| Phase | Feature / 功能 | Description / 描述 |
|---|---|---|
| v2 | Proactive messaging / 主動推送 | Send LINE messages from contact form or sales order |
| v2 | Rich menu integration / 圖文選單整合 | Configure LINE rich menus from Odoo |
| v3 | LINE Login binding / LINE Login 綁定 | Use LINE Login OAuth to link website users to LINE accounts |
| v3 | Multi-channel / 多頻道 | Support multiple LINE Official Accounts per Odoo instance |
| v3 | Analytics / 數據分析 | Message volume, response time, customer satisfaction dashboards |

---

## 14. E2E Test Results / 端到端測試結果

Tested on 2026-03-24. All tests passed.

| # | Test / 測試項目 | Result / 結果 |
|---|---|---|
| 1 | New LINE user -> auto guest + partner + channel | PASS |
| 2 | Existing generic guest -> name updated + partner linked | PASS |
| 3 | Odoo reply -> delivered to LINE (Push API 200) | PASS |
| 4 | Same user repeat message -> no duplicate records | PASS |
| 5 | Partner form view shows LINE ID field | PASS |
| 6 | Image message error handling (graceful fallback) | PASS |
| 7 | Profile API skipped for complete guests (performance) | PASS |
