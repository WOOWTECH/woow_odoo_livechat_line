# LiveChat LINE Integration (`woow_odoo_livechat_line`)

> Bidirectional messaging bridge between LINE Messaging API and Odoo 18 LiveChat / Discuss.

| Field | Value |
|-------|-------|
| **Technical Name** | `woow_odoo_livechat_line` |
| **Version** | 18.0.2.0.0 |
| **Category** | Website/Live Chat |
| **Author** | WoowTech |
| **License** | LGPL-3 |
| **Dependencies** | `im_livechat`, `woow_line_base` |
| **Installable** | Yes |
| **Application** | No |

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Position in the LINE Integration Suite](#position-in-the-line-integration-suite)
4. [Architecture](#architecture)
5. [Message Flow Diagrams](#message-flow-diagrams)
6. [Models Reference](#models-reference)
7. [Wizard Reference](#wizard-reference)
8. [Controller Reference](#controller-reference)
9. [Supported Message Types](#supported-message-types)
10. [Multi-Tenant Architecture](#multi-tenant-architecture)
11. [Security](#security)
12. [File Structure](#file-structure)
13. [Configuration Checklist](#configuration-checklist)
14. [Testing](#testing)
15. [Troubleshooting](#troubleshooting)
16. [For AI Agents](#for-ai-agents)

---

## Overview

This module turns Odoo Discuss into a LINE customer service console. When a customer sends a message through the LINE app, a webhook delivers the event to Odoo, where it is converted into a standard `mail.message` inside a LiveChat `discuss.channel`. Operators reply from Discuss, and the module intercepts those replies and pushes them back to LINE via the Push Message API.

Full support for rich media: text, image, video, audio, file, sticker, and location messages flow in both directions.

---

## Quick Start

Get LINE messages flowing into Odoo Discuss in six steps:

1. **Install the module** -- go to Odoo Apps, search for `woow_odoo_livechat_line`, and click Install. The dependency `woow_line_base` will be installed automatically if not already present.
2. **Create a LiveChat channel** -- navigate to **Live Chat > Configuration > Channels** and create a new channel (e.g. "LINE Support"). Assign at least one operator.
3. **Enable the LINE tab** -- open the channel form, go to the **LINE** tab, and toggle **LINE Integration** on.
4. **Enter credentials** -- paste the **Channel ID** and **Channel Secret** from the LINE Developers Console (Messaging API channel > Basic settings).
5. **Copy the webhook URL** -- the **Webhook URL** field is auto-computed (e.g. `https://your-odoo.com/line/webhook/42`). Click the copy icon, then paste it into the LINE Developers Console under Messaging API > Webhook settings. Enable the webhook toggle there.
6. **Send a test message** -- open the LINE app on your phone, find the Official Account, and send a text message. It should appear in the operator's Discuss inbox within seconds.

> **Tip:** Disable **Auto-reply messages** and **Greeting messages** in the LINE Console to prevent the default LINE bot replies from conflicting with your operators' responses.

---

## Position in the LINE Integration Suite

This module is the third piece of a 3-module LINE integration architecture for Odoo 18:

| # | Module | Purpose |
|---|--------|---------|
| 1 | `woow_line_base` | Core (核心): LINE API client (`line.api.service`), `line.user` identity model, OAuth token management |
| 2 | `woow_odoo_line_liff` | Bridge (橋接): LIFF login, Rich Menu (圖文選單), News push, Audience sync, Insight dashboards |
| 3 | **`woow_odoo_livechat_line`** (this) | LiveChat (即時通訊): LINE <-> Odoo Discuss bidirectional messaging |

**Dependency chain:** This module depends on `woow_line_base` for the `line.api.service` model (token management, profile API, push API, content download) and the `line.user` identity model. It does NOT depend on `woow_odoo_line_liff`.

---

## Architecture

```
+-------------------+         +-------------------------------+         +-------------------+
|                   |         |                               |         |                   |
|   LINE App        |-------->|   Webhook Controller          |-------->|   Discuss UI      |
|   (Customer)      |  POST   |   /line/webhook/<channel>     |  notify |   (Operator)      |
|   LINE 使用者      |<--------|                               |<--------|   客服人員          |
+-------------------+  push   |   HMAC-SHA256 verification    |  reply  +-------------------+
                      message |                               |
                              +--------------+----------------+
                                             |
                              +--------------v----------------+
                              |                               |
                              |   line.api.service            |
                              |   (woow_line_base)            |
                              |   - get_access_token()        |
                              |   - get_profile()             |
                              |   - push_message()            |
                              |   - get_content()             |
                              |   - verify_webhook_signature()|
                              |                               |
                              +-------------------------------+
```

---

## Message Flow Diagrams

### Inbound: LINE --> Odoo (LINE 訊息進入 Odoo)

```
LINE User sends message
        |
        v
LINE Platform POST /line/webhook/<channel_id>
        |
        v
[1] HMAC-SHA256 signature verification (簽章驗證)
        |  (reject if invalid)
        v
[2] _get_or_create_guest(line_user_id)
        |  - Search mail.guest by line_user_id
        |  - If new: fetch LINE profile, create mail.guest + line.user
        |  - If existing with generic name: re-fetch profile
        |  - Auto-bind to res.partner via line.user
        v
[3] _get_or_create_discuss_channel(line_user_id, guest)
        |  - Search by (line_user_id, livechat_channel_id)
        |  - If new: call _get_livechat_discuss_channel_vals()
        |    to assign operator, create channel, add guest member
        |  - Broadcast to operator for live notification
        v
[4] _create_message(message, type, channel, guest)
        |  - Convert LINE message to mail.message body/attachments
        |  - For media: download via line.api.service.get_content()
        |  - message_post() with from_line_webhook=True context
        v
Message appears in Discuss for operator
```

### Outbound: Odoo --> LINE (Odoo 回覆推送至 LINE)

```
Operator types reply in Discuss
        |
        v
[1] mail.message.create() override fires
        |
        v
[2] Loop prevention check (迴圈防止)
        |  - Skip if context has from_line_webhook=True
        |  - Skip if author is guest (not operator)
        |  - Skip if message_type != 'comment'
        v
[3] _send_to_line_if_applicable(message)
        |  - Verify model == 'discuss.channel'
        |  - Verify channel has line_user_id
        v
[4] discuss.channel._notify_line_user(message)
        |  - Get access_token from line.api.service
        |  - Strip HTML tags from body -> text message
        |  - Process each attachment by mimetype:
        |    - image/* -> build_image_message (via /web/image/)
        |    - video/* -> build_video_message + preview PNG
        |    - audio/* -> build_audio_message (60s default duration)
        |    - other   -> build_file_message (Flex Message card)
        |  - Ensure all URLs are HTTPS (_ensure_https_url)
        |  - Generate access_token on attachments for public URLs
        |  - Batch push: max 5 messages per LINE API request
        v
LINE user receives reply in LINE app
```

---

## Models Reference

### 1. `im_livechat.channel` (extension) -- LiveChat 頻道

LINE configuration fields added to the standard LiveChat channel form.

| Field | Type | Attributes | Description |
|-------|------|------------|-------------|
| `line_enabled` | Boolean | default=False | Enable/disable LINE integration for this channel (啟用 LINE 整合) |
| `line_channel_id` | Char | -- | LINE Channel ID from LINE Developers Console |
| `line_channel_secret` | Char | password widget | LINE Channel Secret from LINE Developers Console |
| `line_webhook_url` | Char | computed, readonly | Auto-generated webhook URL: `{web.base.url}/line/webhook/{id}` |

| Method | Description |
|--------|-------------|
| `_check_line_config()` | `@api.constrains` -- validates that `line_channel_id` and `line_channel_secret` are both provided when `line_enabled` is True. Raises `ValidationError` otherwise. |
| `_compute_line_webhook_url()` | Computes the full webhook URL using `web.base.url` system parameter and the record ID. Returns `False` for unsaved records. |

**View:** Adds a "LINE" tab after the "Channel Rules" page in the LiveChat channel form (`im_livechat.im_livechat_channel_view_form`). The credentials section is conditionally visible (`invisible="not line_enabled"`). The webhook URL field uses the `CopyClipboardChar` widget for one-click copying.

---

### 2. `discuss.channel` (extension) -- 討論頻道

Associates a Discuss conversation with a LINE user and handles outbound message delivery.

| Field | Type | Attributes | Description |
|-------|------|------------|-------------|
| `line_user_id` | Char | indexed | LINE User ID for this conversation |
| `line_display_name` | Char | -- | Cached LINE display name (LINE 顯示名稱) |
| `line_picture_url` | Char | -- | Cached LINE profile picture URL |

| Method | Signature | Description |
|--------|-----------|-------------|
| `_notify_line_user` | `(message)` | Core outbound push. Strips HTML from body, processes attachments by mimetype, enforces HTTPS on all URLs, generates `access_token` on `ir.attachment` records, builds LINE message objects, and sends via `line.api.service.push_message()` in batches of 5. |
| `_ensure_https_url` | `(url) -> str or None` | Converts `http://` URLs to `https://`. Returns `None` for non-HTTP URLs. Required because LINE Messaging API mandates HTTPS for all media content URLs. |

**Outbound attachment handling by mimetype:**

| Mimetype pattern | LINE message type | Odoo URL endpoint | Notes |
|------------------|-------------------|--------------------|-------|
| `image/*` | Image message | `/web/image/{id}?access_token=...` | Falls back to text link if HTTPS conversion fails |
| `video/*` | Video message | `/web/content/{id}?access_token=...` | Uses static `video_preview.png` as preview image |
| `audio/*` | Audio message | `/web/content/{id}?access_token=...` | Hardcoded 60,000ms (60s) duration estimate |
| Other | Flex Message card | `/web/content/{id}?access_token=...&download=true` | Rich card with filename, size, and download link via `build_file_message()` |

---

### 3. `mail.guest` (extension) -- 訪客

Extends the guest model to track LINE identity and linked contacts.

| Field | Type | Attributes | Description |
|-------|------|------------|-------------|
| `line_user_id` | Char | indexed, unique SQL constraint | LINE User ID. Constraint `line_user_id_unique` prevents duplicate guests for the same LINE user. |
| `line_partner_id` | Many2one `res.partner` | -- | Contact linked to this LINE user (關聯的聯絡人) |

| Method | Signature | Description |
|--------|-----------|-------------|
| `action_link_to_partner` | `()` | Opens the `line.guest.link.partner.wizard` in a modal dialog (`target='new'`) with the current guest pre-filled via `default_guest_id` context. |

---

### 4. `mail.message` (override) -- 訊息

Intercepts operator replies to trigger outbound LINE delivery.

| Method | Signature | Description |
|--------|-----------|-------------|
| `create` | `(vals_list)` | `@api.model_create_multi` override. After `super().create()`, checks each message. Skips if `from_line_webhook` context flag is set (loop prevention). Skips if author is a guest (`author_guest_id` is set) or if `message_type` is not `'comment'`. Otherwise calls `_send_to_line_if_applicable()`. |
| `_send_to_line_if_applicable` | `(message)` | Validates that the message belongs to a `discuss.channel` with a `line_user_id`. If so, calls `discuss_channel._notify_line_user(message)`. Wrapped in try/except -- errors are logged but never raised (non-blocking). |

---

## Wizard Reference

### `line.guest.link.partner.wizard` (訪客綁定聯絡人精靈)

Transient model that allows operators to bind a LINE guest to an existing `res.partner` contact.

| Field | Type | Attributes | Description |
|-------|------|------------|-------------|
| `guest_id` | Many2one `mail.guest` | required, readonly | The guest being linked (pre-filled from context) |
| `partner_id` | Many2one `res.partner` | required, `no_create=True` | The target contact to link. The `no_create` option prevents creating new contacts from this wizard. |

| Method | Signature | Description |
|--------|-----------|-------------|
| `action_link` | `()` | Sets `line_partner_id` and updates `name` on the guest record. Then searches for an existing `line.user` record by `line_uid`. If found, updates its `partner_id`. If not found, creates one via `create_or_update_from_webhook()` and then binds the partner. Returns `ir.actions.act_window_close`. |

**Security:** Access is restricted to the `im_livechat.im_livechat_group_user` group (LiveChat operators).

**View:** Simple form with `partner_id` field (guest_id is hidden). Footer has "Link" (primary) and "Cancel" buttons.

---

## Controller Reference

### `LineWebhookController` (`controllers/webhook.py`)

| Route | Auth | Type | CSRF | Methods |
|-------|------|------|------|---------|
| `/line/webhook/<int:channel_id>` | public | json | disabled | POST |

#### Main endpoint: `line_webhook(channel_id)`

1. Looks up `im_livechat.channel` by `channel_id` (via `sudo`)
2. Rejects if channel does not exist or `line_enabled` is False
3. Reads raw request body and `X-Line-Signature` header
4. Verifies HMAC-SHA256 signature via `line.api.service.verify_webhook_signature()`
5. Parses JSON body, iterates over `events[]`
6. Routes each event to the appropriate handler (each in its own try/except)
7. Returns `{}` (LINE expects HTTP 200 with empty response)

#### Webhook route conflict with `woow_odoo_line_liff`

When both `woow_odoo_livechat_line` and `woow_odoo_line_liff` are installed on the same Odoo instance, both modules register a handler for `/line/webhook/<int:channel_id>`. In this scenario:

| Mode | Which controller handles the webhook | How this module is invoked |
|------|--------------------------------------|----------------------------|
| **Co-installed** (common) | `woow_odoo_line_liff`'s controller takes precedence. It processes LIFF-specific events (e.g., Rich Menu postbacks, audience syncs) and then calls `_forward_to_livechat()` to programmatically invoke this module's message handling logic for `message` and `follow` events. | Programmatically via `_forward_to_livechat()` -- no direct HTTP route hit. |
| **Standalone** (this module only) | This module's `LineWebhookController` handles `/line/webhook/<int:channel_id>` directly. | Direct HTTP POST from LINE Platform. |

**Key clarification on the URL parameter:** The `channel_id` in `/line/webhook/<int:channel_id>` refers to the `im_livechat.channel` record ID -- the LiveChat channel configured under **Live Chat > Configuration > Channels**. It is NOT the `line.liff.config` record ID used by `woow_odoo_line_liff`. When registering the webhook URL in the LINE Developers Console, always use the ID shown in the **Webhook URL** computed field on the LiveChat channel form.

#### Event routing: `_process_event(event, livechat_channel)`

| Event type | Handler | Description |
|------------|---------|-------------|
| `message` | `_handle_message_event()` | Processes inbound user messages (all types) |
| `follow` | `_handle_follow_event()` | Fetches profile and creates/updates `line.user` when user follows the Official Account |
| `unfollow` | (logged only) | No action taken, info-level log for audit |
| Other | (debug logged) | Silently ignored |

#### Guest management: `_get_or_create_guest(line_user_id, livechat_channel)`

- Searches `mail.guest` by `line_user_id`
- **New guest:** Fetches LINE profile via `_fetch_line_profile()`, creates `mail.guest` with display name (falls back to `"LINE User"`), calls `line.user.create_or_update_from_webhook()` to establish identity in `woow_line_base`, auto-links `line_partner_id` if partner exists on the `line.user`
- **Existing guest with generic name** (`"LINE User"` or empty) **or missing partner:** Re-fetches profile to update display name and re-checks partner binding
- **Existing guest with proper name and partner:** No API call (profile caching strategy)

#### Profile fetching: `_fetch_line_profile(line_user_id, livechat_channel)`

Retrieves the LINE user's display name and profile picture URL from the LINE Platform.

| Aspect | Detail |
|--------|--------|
| **Parameters** | `line_user_id` (`str`) -- the LINE user's unique identifier (e.g. `U1234...`). `livechat_channel` (`im_livechat.channel` recordset) -- used to read `line_channel_id` and `line_channel_secret` for API authentication. |
| **Returns** | `dict` with keys `displayName` (str), `pictureUrl` (str, optional), `statusMessage` (str, optional) on success. Returns `{}` (empty dict) on any failure (network error, invalid token, expired user, etc.). |
| **Called by** | `_get_or_create_guest()` -- invoked when creating a new guest or when an existing guest still has the generic name `"LINE User"`. |
| **Implementation** | Calls `line.api.service.get_access_token(channel_id, channel_secret)` to obtain an OAuth token, then calls `line.api.service.get_profile(line_user_id, access_token)`. Errors are caught and logged; the empty dict fallback ensures guest creation proceeds with the generic name. |

#### Channel management: `_get_or_create_discuss_channel(line_user_id, guest, livechat_channel)`

- Searches by `(line_user_id, livechat_channel_id)` -- ensures multi-tenant isolation
- **New channel:** Calls `livechat_channel._get_livechat_discuss_channel_vals()` for standard operator assignment. If this returns falsy (all operators offline), falls back to the first user in `livechat_channel.user_ids` as a fallback operator. Creates channel with `channel_type='livechat'`, sets `line_user_id` and `line_display_name`, adds guest as channel member via `add_members(guest_ids=[guest.id])`, broadcasts to assigned operator via `_broadcast()`
- **Existing channel:** Updates `line_display_name` and `anonymous_name` if the guest name changed

#### Message creation: `_create_message(message, message_type, discuss_channel, guest, livechat_channel)`

Converts LINE message format into `mail.message` via `message_post()`. Two critical context values:
- `from_line_webhook=True` -- prevents outbound loop
- `guest=guest` -- sets proper author attribution (`author_guest_id`)

Uses `attachments=[(filename, content)]` parameter (list of tuples) for media, which lets Odoo create the `ir.attachment` records internally.

#### Content download: `_download_line_content(message_id, message_type, message, livechat_channel)`

- Gets access token from `line.api.service`
- Downloads binary content via `line.api.service.get_content(message_id)`
- Handles both legacy (raw bytes) and new `(content_bytes, content_type)` tuple return formats
- Determines filename and mimetype from `Content-Type` header with fallback to message type
- Returns `(filename, content_bytes, mimetype)` tuple, or `None` on failure

**Extension map for content type detection:**

| Content-Type | Extension |
|--------------|-----------|
| `image/jpeg` | `.jpg` |
| `image/png` | `.png` |
| `image/gif` | `.gif` |
| `video/mp4` | `.mp4` |
| `audio/m4a` | `.m4a` |
| `audio/x-m4a` | `.m4a` |
| `audio/mp4` | `.m4a` |
| `audio/mpeg` | `.mp3` |
| `application/pdf` | `.pdf` |

#### Debug logging

The controller writes to two log destinations:
1. **Odoo logger** (`_logger`): Standard `logging.getLogger(__name__)`, prefix `LINE webhook:`
2. **Debug file** (`/tmp/line_webhook_debug.log`): Append-only file via `_log_to_file()` for containerized environments where Odoo log access is difficult

---

## Supported Message Types

### Inbound (LINE --> Odoo) -- 接收訊息

| LINE type | Odoo representation | Details |
|-----------|---------------------|---------|
| `text` (文字) | `body` (plain text) | `message.text` stored directly |
| `image` (圖片) | `ir.attachment` (image) | Downloaded via Content API, stored as `line_image_{id}.jpg` |
| `video` (影片) | `ir.attachment` (video) | Downloaded via Content API, stored as `line_video_{id}.mp4` |
| `audio` (音訊) | `ir.attachment` (audio) | Downloaded via Content API, stored as `line_audio_{id}.m4a` |
| `file` (檔案) | `ir.attachment` (file) | Downloaded via Content API, original `fileName` preserved |
| `sticker` (貼圖) | `body` text placeholder | Format: `[Sticker: {packageId}/{stickerId}]` |
| `location` (位置) | `body` with HTML | XSS-safe via `markupsafe.escape()`. Includes Google Maps link: `https://www.google.com/maps?q={lat},{lng}` |

### Outbound (Odoo --> LINE) -- 發送訊息

| Odoo content | LINE message type | Details |
|--------------|-------------------|---------|
| Text body (HTML) | Text message | HTML tags stripped via regex `<[^>]+>` |
| Image attachment (`image/*`) | Image message | URL: `/web/image/{id}?access_token=...` |
| Video attachment (`video/*`) | Video message | URL: `/web/content/{id}?access_token=...`, preview: static `video_preview.png` |
| Audio attachment (`audio/*`) | Audio message | URL: `/web/content/{id}?access_token=...`, duration: 60,000ms default |
| Other attachment | Flex Message card | Built via `line.api.service.build_file_message(name, url, file_size)` |

---

## Multi-Tenant Architecture

Each `im_livechat.channel` record stores its own set of LINE credentials (`line_channel_id`, `line_channel_secret`). This enables multiple LINE Official Accounts to connect to a single Odoo instance, each routed to a different LiveChat channel with its own operator team.

**Isolation guarantees:**

| Layer | Mechanism |
|-------|-----------|
| **Credentials** | Each channel gets its own OAuth access token from LINE via `line.api.service.get_access_token(channel_id, channel_secret)` |
| **Webhook routing** | The URL path contains the channel ID: `/line/webhook/<channel_id>`. LINE delivers events only to the registered webhook URL |
| **Conversation scoping** | `discuss.channel` records are searched by composite key `(line_user_id, livechat_channel_id)`. A LINE user chatting with two different Official Accounts gets two separate Discuss channels |
| **Outbound routing** | The outbound path reads `livechat_channel_id` from the `discuss.channel`, so replies always use the correct channel's credentials. No cross-tenant routing is possible |

---

## Security

### Access Control (存取控制)

| Model | Group | Read | Write | Create | Delete |
|-------|-------|:----:|:-----:|:------:|:------:|
| `line.guest.link.partner.wizard` | `im_livechat.im_livechat_group_user` | Yes | Yes | Yes | Yes |

All other models (`im_livechat.channel`, `discuss.channel`, `mail.guest`, `mail.message`) inherit their existing Odoo ACL rules. The module adds fields but does not change access control on those models.

### Webhook Security (Webhook 安全)

| Layer | Mechanism |
|-------|-----------|
| HMAC-SHA256 | Every incoming POST is validated against the channel's `line_channel_secret`. Invalid signatures are silently rejected (200 OK returned, no processing). |
| Channel check | Disabled channels (`line_enabled=False`) and non-existent channel IDs reject all webhook events. |
| No CSRF | The webhook route has `csrf=False` since LINE cannot send CSRF tokens. Authentication is via HMAC signature instead. |
| XSS prevention | Location message `title` and `address` are escaped via `markupsafe.escape()` before being rendered as HTML in the message body. |

### Media URL Security

- All `ir.attachment` records served to LINE receive a generated `access_token` via `attachment.sudo().generate_access_token()`
- URLs include the `access_token` query parameter: `/web/image/{id}?access_token={token}`
- Without the token, Odoo returns 403 for non-authenticated requests

### Webhook Retry & Deduplication (Webhook 重試與去重)

LINE Platform retries webhook delivery when it receives a non-200 HTTP response or when the server does not respond within 60 seconds. This module mitigates retry-related issues as follows:

| Aspect | Behavior |
|--------|----------|
| **HTTP response** | The webhook controller always returns `{}` with HTTP 200 OK, even when event processing fails internally. This prevents LINE from retrying. |
| **Error isolation** | Each event in the `events[]` array is processed in its own try/except block. A failure in one event does not cause a non-200 response that would trigger a retry of the entire payload. |
| **Deduplication** | This module does **not** deduplicate by `webhookEventId`. LINE includes a unique `webhookEventId` in each event, but this module does not track or check it. |
| **Practical risk** | Retries are rare in practice because the controller consistently returns 200. Duplicate messages would only occur if the Odoo server crashes or times out mid-processing (>60s), which is uncommon for the lightweight webhook handler. |

> **Note:** If your deployment experiences timeouts (e.g., slow database, large attachment downloads), consider adding deduplication by storing processed `webhookEventId` values in a transient model or cache.

---

## File Structure

```
woow_odoo_livechat_line/
|-- __init__.py
|-- __manifest__.py
|-- controllers/
|   |-- __init__.py
|   +-- webhook.py                              # LINE webhook endpoint + HMAC verification
|-- models/
|   |-- __init__.py
|   |-- im_livechat_channel.py                  # LINE config fields on LiveChat channel
|   |-- discuss_channel.py                      # LINE user fields + _notify_line_user()
|   |-- mail_guest.py                           # Guest with line_user_id + unique constraint
|   +-- mail_message.py                         # create() override for outbound delivery
|-- wizard/
|   |-- __init__.py
|   |-- line_guest_link_partner_wizard.py        # Guest-to-partner linking logic
|   +-- line_guest_link_partner_wizard_views.xml # Wizard form view
|-- views/
|   +-- im_livechat_channel_views.xml           # LINE tab on LiveChat channel form
|-- security/
|   +-- ir.model.access.csv                     # ACL for wizard (LiveChat operators)
|-- static/
|   |-- description/
|   |   |-- icon.png                            # Module icon
|   |   +-- index.html                          # Odoo Apps store description page
|   +-- img/
|       |-- video_preview.png                   # Default video preview thumbnail
|       +-- video_preview.svg                   # SVG source for video preview
|-- tests/
|   |-- __init__.py
|   |-- common.py                               # Test infrastructure: mixin, mocks, helpers
|   |-- test_phase06_deployment.py              # 17 tests
|   |-- test_phase07_contact_binding.py         # 18 tests
|   |-- test_phase08_multi_tenant.py            # 14 tests
|   |-- test_phase09_https_proxy.py             # 14 tests
|   |-- test_phase10_fault_recovery.py          # 16 tests
|   |-- test_phase11_monitoring.py              # 13 tests
|   |-- test_phase12_data_governance.py         # 18 tests
|   +-- test_phase13_operations.py              # 18 tests
|-- i18n/
|   |-- woow_odoo_livechat_line.pot             # Translation template
|   +-- zh_TW.po                                # Traditional Chinese translation
+-- docs/
    |-- plans/                                  # Design documents and PRDs
    +-- screenshots/                            # UI screenshots for documentation
```

---

## Configuration Checklist

### LINE Developers Console (LINE 開發者後台)

- [ ] Create a **Messaging API Channel** (or use an existing LINE Official Account)
- [ ] Note the **Channel ID** (Basic settings page)
- [ ] Note the **Channel Secret** (Basic settings page)
- [ ] Enable **Webhooks** in the Messaging API settings
- [ ] Set the **Webhook URL** to `https://<your-odoo-domain>/line/webhook/<livechat_channel_id>`
- [ ] Disable **Auto-reply messages** (recommended, to avoid LINE default bot replies conflicting with operator responses)
- [ ] Disable **Greeting messages** (optional, or use `follow` event handling instead)

### Odoo Instance (Odoo 設定)

- [ ] Ensure `woow_line_base` module is installed (provides `line.api.service`)
- [ ] Install `woow_odoo_livechat_line` from Apps
- [ ] Ensure the Odoo instance is served over **HTTPS** (set `web.base.url` system parameter to your public HTTPS domain)
- [ ] Navigate to **Live Chat > Configuration > Channels**, open or create a channel
- [ ] Go to the **LINE** tab:
  - [ ] Enable the **LINE Integration** toggle
  - [ ] Enter **LINE Channel ID**
  - [ ] Enter **LINE Channel Secret** (stored with password widget)
  - [ ] Copy the computed **Webhook URL** and paste it into LINE Developers Console
- [ ] Ensure at least one **operator** is assigned to the LiveChat channel
- [ ] Send a test message from LINE and verify it appears in Discuss

---

## Testing

The module includes **8 test phases with 128 tests total**, all tagged `post_install`.

All tests extend `LineTransactionCase` (from `tests/common.py`) which provides:
- A pre-configured LiveChat channel with LINE credentials
- An operator user with `im_livechat_group_user` membership
- Helper methods: `_create_line_guest()`, `_create_line_discuss_channel()`, `_call_controller_directly()`
- Mock factories for LINE API responses: `mock_line_token_response()`, `mock_line_profile_response()`, `mock_line_push_response()`, `mock_line_content_response()`
- URL-based request routing mocks: `route_mock_post()`, `route_mock_get()`
- HMAC-SHA256 signature computation: `make_line_signature()`
- Webhook event builders: `make_webhook_event()`, `make_webhook_body()`

| Phase | File | Tests | Coverage Area |
|-------|------|:-----:|---------------|
| 06 | `test_phase06_deployment.py` | 17 | Module installation, webhook endpoint, message creation, event routing |
| 07 | `test_phase07_contact_binding.py` | 18 | Guest-to-partner linking, wizard behavior, auto-binding, line.user sync |
| 08 | `test_phase08_multi_tenant.py` | 14 | Credential isolation, per-channel routing, cross-tenant prevention |
| 09 | `test_phase09_https_proxy.py` | 14 | HTTPS URL enforcement, http-to-https conversion, edge cases |
| 10 | `test_phase10_fault_recovery.py` | 16 | API failures, download errors, missing tokens, non-blocking error handling |
| 11 | `test_phase11_monitoring.py` | 13 | Log output verification, debug file writing, event logging |
| 12 | `test_phase12_data_governance.py` | 18 | SQL unique constraints, data integrity, validation errors |
| 13 | `test_phase13_operations.py` | 18 | Operational scenarios: profile updates, channel reuse, batch sending |

### Running Tests

```bash
# Run all tests for this module
odoo-bin -d <database> -i woow_odoo_livechat_line --test-enable --stop-after-init

# Run all tests with the post_install tag (recommended for CI)
odoo-bin -d <database> -i woow_odoo_livechat_line --test-enable --stop-after-init --test-tags=post_install

# Run a single test class (e.g., all tests in Phase 06)
odoo-bin -d <database> -i woow_odoo_livechat_line --test-enable --stop-after-init -k TestPhase06Deployment

# Run a single test method
odoo-bin -d <database> -i woow_odoo_livechat_line --test-enable --stop-after-init -k test_webhook_message_text

# Run tests with verbose logging to see LINE webhook debug output
odoo-bin -d <database> -i woow_odoo_livechat_line --test-enable --stop-after-init --log-level=debug
```

> **Note:** The `-k` flag filters test classes or methods by name substring. All tests are `post_install`, meaning the module must be installed (or installed via `-i`) before tests run.

---

## Troubleshooting

Common issues and their solutions:

| Symptom | Cause | Fix |
|---------|-------|-----|
| Webhook returns 200 but no message appears in Discuss | HMAC-SHA256 signature verification failed silently (invalid signatures are rejected without error response) | Verify that the `line_channel_secret` in Odoo matches the Channel Secret in the LINE Developers Console. Check Odoo logs for `LINE webhook: Signature verification failed`. |
| Operator replies do not reach the LINE user | LINE Channel Access Token is expired or not issued | Go to the LINE Developers Console > Messaging API > Channel Access Token and re-issue a long-lived token. The `woow_line_base` module caches tokens in memory; restart Odoo if needed. |
| Guest name shows as "LINE User" instead of actual name | Profile API call failed (network error, rate limit, or blocked user) | Check Odoo logs for `LINE webhook: Failed to fetch profile`. The profile will be re-fetched on the user's next message if the name is still generic. |
| Duplicate messages appear in Discuss | LINE retried the webhook because a previous request timed out or returned non-200 | See the [Webhook Retry & Deduplication](#webhook-retry--deduplication-webhook-重試與去重) section. Ensure Odoo responds within 60 seconds. |
| Images sent from Odoo appear as text links in LINE | `web.base.url` system parameter is set to `http://` instead of `https://` | Set `web.base.url` to your public HTTPS URL in **Settings > Technical > System Parameters**. LINE Messaging API rejects all `http://` media URLs. |
| Video messages show a blank preview in LINE | The static `video_preview.png` file is missing or inaccessible | Verify that `/woow_odoo_livechat_line/static/img/video_preview.png` exists and is served correctly. Test by visiting the URL directly in a browser. |
| Webhook URL shows `False` in the channel form | The LiveChat channel record has not been saved yet | Save the channel record first. The webhook URL is computed from the record ID, which does not exist until the first save. |
| Messages from LINE appear but operator replies fail silently | `_send_to_line_if_applicable()` caught an exception | Check Odoo logs for `LINE push error` or `Error sending to LINE`. The error is logged but never raised to avoid blocking the operator's Discuss workflow. |

---

## For AI Agents

This section provides structured guidance for AI agents (coding assistants, automation bots, LLM-based tools) that need to understand, configure, extend, or debug this module.

### How to set up a new LINE channel integration

1. **Create the LiveChat channel in Odoo** (or use an existing one):
   ```python
   channel = env['im_livechat.channel'].create({
       'name': 'My LINE Support',
       'user_ids': [(4, operator_user.id)],
       'line_enabled': True,
       'line_channel_id': '<from LINE Developers Console>',
       'line_channel_secret': '<from LINE Developers Console>',
   })
   ```
2. **Read the computed webhook URL:**
   ```python
   print(channel.line_webhook_url)
   # e.g. https://your-odoo.com/line/webhook/42
   ```
3. **Register this URL** in the LINE Developers Console under Messaging API > Webhook settings.
4. **Verify** by having a LINE user send a message. Check Odoo logs for `LINE webhook:` entries.

### How the webhook processes events

The webhook controller at `/line/webhook/<int:channel_id>`:

1. Receives a JSON POST from LINE Platform
2. Reads `X-Line-Signature` header and raw body bytes
3. Calls `line.api.service.verify_webhook_signature(body, signature, channel_secret=...)` -- this computes `HMAC-SHA256(channel_secret, body)` and compares the base64-encoded digest against the header value
4. Parses JSON body to extract `events[]` array
5. For each event (each in its own try/except):
   - `message` events: `_handle_message_event()` --> guest lookup --> channel lookup --> `_create_message()`
   - `follow` events: `_handle_follow_event()` --> fetch profile, create/update `line.user` in `woow_line_base`
   - `unfollow` events: logged only (no cleanup or deletion)
   - Other events: debug-logged and ignored
6. Returns `{}` (HTTP 200 OK is all LINE requires)

**Important:** All event processing is wrapped in try/except. Errors are logged but never raised, because LINE would retry failed webhooks and potentially create duplicate messages.

### How outbound messages are triggered

The `mail.message.create()` override is the sole entry point:

```
mail.message.create() called
    |
    v
Check context: from_line_webhook? --> skip (loop prevention)
    |
    v
Check author: has author_guest_id? --> skip (guests are LINE users, not operators)
    |
    v
Check author: has author_id and message_type == 'comment'? --> proceed
    |
    v
_send_to_line_if_applicable(message)
    |-- Check model == 'discuss.channel' and res_id exists
    |-- Browse discuss.channel, check line_user_id is set
    |-- Call discuss_channel._notify_line_user(message)
         |-- Get access_token via line.api.service
         |-- Strip HTML tags, build text message
         |-- For each attachment:
         |   |-- Generate access_token on ir.attachment
         |   |-- Build URL with access_token
         |   |-- Enforce HTTPS via _ensure_https_url()
         |   +-- Build appropriate LINE message type
         +-- Batch send via push_message() (max 5 per request)
```

### Multi-tenant credential isolation

- Each `im_livechat.channel` has its own `line_channel_id` and `line_channel_secret` fields
- The webhook URL path includes the channel ID (`/line/webhook/42`), so LINE delivers events to the correct channel
- `discuss.channel` records store `livechat_channel_id` as a foreign key, so outbound replies always use the correct credentials
- The search for existing conversations uses `(line_user_id, livechat_channel_id)` as composite key -- a LINE user talking to two different Official Accounts gets two separate Discuss conversations with two different operator teams

### Loop prevention mechanism

Without loop prevention, an infinite loop would occur:

```
LINE user sends message
  -> webhook creates mail.message in Discuss
    -> mail.message.create() override detects new message
      -> sends message back to LINE user (WRONG!)
        -> LINE user "receives" their own message
```

The solution uses the `from_line_webhook` context flag:

1. When the webhook creates a message, it sets `from_line_webhook=True` in context:
   ```python
   discuss_channel.with_context(from_line_webhook=True).message_post(...)
   ```
2. In `mail.message.create()`, the override checks this flag first:
   ```python
   if self.env.context.get('from_line_webhook'):
       return messages  # Skip outbound delivery
   ```
3. Additionally, messages authored by guests (`author_guest_id` is truthy) are always skipped, providing a second layer of protection.
4. Only messages with `message_type == 'comment'` are forwarded -- system messages, notifications, etc. are ignored.

### Media handling patterns

**Inbound (download from LINE):**
```python
# In _download_line_content():
access_token = line_api.get_access_token(channel_id=..., channel_secret=...)
result = line_api.get_content(message_id, access_token=access_token)
# result is (content_bytes, content_type) tuple or raw bytes (legacy)
# Returns (filename, content_bytes, mimetype) or None on failure

# In _create_message():
# Attachments are passed via the `attachments` parameter of message_post()
# as a list of (filename, content_bytes) tuples -- Odoo creates ir.attachment internally:
discuss_channel.message_post(
    body='',
    attachments=[(filename, content)],
    message_type='comment',
    subtype_xmlid='mail.mt_comment',
)
```

**Outbound (push to LINE):**
```python
# In _notify_line_user():
# 1. Generate access_token on ir.attachment for public URL access
if not attachment.access_token:
    attachment.sudo().generate_access_token()

# 2. Build URL with access_token
image_url = f'{base_url}/web/image/{attachment.id}?access_token={att_token}'

# 3. Enforce HTTPS (LINE requires it)
image_url = self._ensure_https_url(image_url)

# 4. Build LINE message object via line.api.service
messages.append(line_api.build_image_message(image_url))

# 5. Push to LINE (batched, max 5 per request)
for i in range(0, len(messages), 5):
    batch = messages[i:i + 5]
    line_api.push_message(line_user_id, batch, access_token=access_token)
```

**Key points for media:**
- LINE Content API URLs are temporary (message_id based) -- content must be downloaded and stored as `ir.attachment` immediately during webhook processing
- Odoo attachment URLs need `access_token` for unauthenticated access by LINE's servers
- All outbound URLs must be HTTPS; `_ensure_https_url()` handles `http://` to `https://` conversion
- Video preview uses a static fallback PNG at `/woow_odoo_livechat_line/static/img/video_preview.png`
- Audio duration is hardcoded to 60,000ms (LINE requires a duration for audio messages but there is no reliable way to determine it server-side without additional dependencies)
- For file-type messages, the original `fileName` from LINE is preserved

### Error handling philosophy (non-blocking, logged)

The module follows a strict **non-blocking** error handling policy:

1. **Webhook level:** Each event is processed in its own try/except. If one event fails, the remaining events are still processed. The webhook always returns `{}` with HTTP 200.
2. **Outbound level:** `_send_to_line_if_applicable()` catches all exceptions via `except Exception as e` and logs them with `_logger.error()`. An operator's message is always saved in Discuss even if LINE delivery fails.
3. **Token failures:** If `get_access_token()` returns `None`, the method returns early. The message is lost on the LINE side but preserved in Odoo.
4. **Content download failures:** If media download fails, a placeholder like `[Image - download failed]` is posted as the body text instead.
5. **HTTPS conversion:** If a URL cannot be made HTTPS, a text fallback with the plain URL is sent instead of the rich media message.

**Why non-blocking?** LINE retries webhooks that return HTTP errors. If we raised exceptions (causing 5xx responses), LINE would send the same event repeatedly, potentially creating duplicate messages. By always returning 200 OK and logging errors internally, we prevent retry storms.

### How to extend for new message types

To support a new LINE message type (e.g., `imagemap`, `template`, `flex`):

**Inbound (LINE --> Odoo):**

1. Edit `controllers/webhook.py`, method `_create_message()`, add a new `elif` block:
   ```python
   elif message_type == 'imagemap':
       # Extract relevant fields from the LINE message dict
       base_url_img = message.get('baseUrl')
       body = f'[Imagemap: {base_url_img}]'
       # Or download and create attachment if desired
   ```
2. No changes needed in models -- `_create_message()` calls `message_post()` which handles any body/attachment combination.

**Outbound (Odoo --> LINE):**

1. Edit `models/discuss_channel.py`, method `_notify_line_user()`, add a new mimetype branch:
   ```python
   elif mimetype == 'application/x-custom':
       custom_url = f'{base_url}/web/content/{attachment.id}?access_token={att_token}'
       custom_url = self._ensure_https_url(custom_url)
       if custom_url:
           messages.append(line_api.build_custom_message(...))
   ```
2. You may also need to add a corresponding `build_*_message()` method in `woow_line_base`'s `line.api.service` if the LINE message format is not yet supported there.

**Testing:**

1. Add test cases in the appropriate phase file (typically `test_phase06_deployment.py` for basic messaging).
2. Use `make_webhook_event()` from `tests/common.py`:
   ```python
   event = make_webhook_event(message_type='imagemap', ...)
   ```
3. Use `_call_controller_directly()` from the `LineTestMixin` to invoke the webhook without HTTP:
   ```python
   self._call_controller_directly(self.livechat_channel.id, [event])
   ```
4. Mock LINE API responses using `route_mock_post` and `route_mock_get` from `tests/common.py` with `unittest.mock.patch('requests.post', side_effect=route_mock_post)`.

### Key implementation constants

| Constant | Value | Location | Purpose |
|----------|-------|----------|---------|
| Max messages per push | 5 | `discuss_channel.py` line 140 | LINE Push API limit per request |
| Default audio duration | 60,000 ms | `discuss_channel.py` line 116 | LINE requires duration for audio messages |
| Generic guest name | `"LINE User"` | `webhook.py` line 186 | Fallback when profile fetch fails |
| Token validity | 30 days | `woow_line_base` (upstream) | Access token cache TTL (in-memory, reset on restart) |
| Video preview path | `static/img/video_preview.png` | `discuss_channel.py` line 101 | Static fallback for video thumbnails |
| Debug log file | `/tmp/line_webhook_debug.log` | `webhook.py` line 18 | Append-only debug log for containerized envs |

---

## Webhook Route Conflict with woow_odoo_line_liff

When **both** modules are installed, the bridge module (`woow_odoo_line_liff`) takes precedence for the `/line/webhook/<int:config_id>` route due to Odoo's route registration order.

### Standalone Mode (this module only)

```
LINE Platform → POST /line/webhook/<int:channel_id>
                                        ↑
                                im_livechat.channel.id
```

The URL parameter is `im_livechat.channel.id`. Credential lookup uses the livechat channel's LINE fields.

### With Bridge Module Installed

```
LINE Platform → POST /line/webhook/<int:config_id>
    │                                   ↑
    │                          line.liff.config.id
    ▼
woow_odoo_line_liff webhook (handles ALL events)
    │
    └── _forward_to_livechat(event)  ← dynamic import
        │
        ▼
    THIS module's controller (invoked programmatically)
```

**Consequence:** This module's webhook controller is **NEVER called directly via HTTP** when `woow_odoo_line_liff` is installed. It is only invoked programmatically via the bridge module's forwarding mechanism.

---

## Webhook Retries & Deduplication

LINE retries webhook delivery if the endpoint returns a non-200 status or times out (60 seconds). This module **always returns HTTP 200** (even on internal errors) to prevent retries.

**Known limitation:** The module does **NOT** perform deduplication based on `event.webhookEventId`. If LINE retries despite receiving 200 (rare, caused by network issues), duplicate `mail.message` records may be created in Discuss.

**Mitigation:** In practice, LINE retries are rare when the endpoint consistently returns 200. If deduplication is critical, override `_create_message()` to check for recent messages with identical content within a short time window.

---

## mail.guest Unique Constraint

Each LINE user gets a unique `mail.guest` record (identified by `line_user_id` field). If the constraint fails (e.g., during concurrent webhook processing), the exception is caught and the existing guest is reused.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Webhook returns 200 but no message in Discuss | Signature verification failed silently | Check `line_channel_secret` on livechat channel matches LINE Console |
| Messages appear in Discuss but replies don't reach LINE | `access_token` is None or expired | Re-issue long-lived token in LINE Console |
| "LINE User" generic name persists | Profile API failed (rate limit or invalid token) | Check logs for `LINE webhook: Profile fetch failed` |
| Duplicate messages in Discuss | LINE retried the webhook | Check network stability; see deduplication note above |
| Images show as text links in LINE | `web.base.url` is HTTP, not HTTPS | Set `web.base.url` to HTTPS domain |
| Video messages show blank preview | `video_preview.png` missing or inaccessible | Verify file exists at `static/img/video_preview.png` |
| Livechat channel shows no LINE messages | Channel `line_channel_id` not set | Edit livechat channel → fill LINE Messaging Channel ID |
| Reply goes to wrong LINE user | `mail.guest.line_user_id` mismatch | Check guest record binding; may need manual fix |
| Audio message has wrong duration | Hardcoded 60s default | Known limitation; LINE requires duration but Odoo doesn't extract it |

---

## Running Individual Tests

```bash
# All tests
odoo-bin -d testdb -i woow_odoo_livechat_line --test-enable --stop-after-init

# Single test class
odoo-bin -d testdb --test-tags=/woow_odoo_livechat_line -k TestWebhookMessage

# Single test method
odoo-bin -d testdb --test-tags=/woow_odoo_livechat_line -k test_webhook_message_text

# Using make_webhook_event helper in tests:
# from woow_odoo_livechat_line.tests.common import make_webhook_event
# event = make_webhook_event(message_type='text', text='Hello')
```
