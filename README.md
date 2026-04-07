<p align="center">
  <img src="static/description/icon.png" alt="LiveChat LINE Integration" width="120"/>
</p>

<h1 align="center">LiveChat LINE Integration</h1>

<p align="center">
  Integrate LINE Messaging API with Odoo LiveChat for seamless bidirectional communication between LINE users and Odoo operators through the standard Discuss interface.
</p>

<p align="center">
  <a href="#overview">Overview</a> &bull;
  <a href="#features">Features</a> &bull;
  <a href="#architecture">Architecture</a> &bull;
  <a href="#screenshots">Screenshots</a> &bull;
  <a href="#installation">Installation</a> &bull;
  <a href="#configuration">Configuration</a> &bull;
  <a href="#security">Security</a> &bull;
  <a href="#api-reference">API Reference</a> &bull;
  <a href="#testing">Testing</a> &bull;
  <a href="#changelog">Changelog</a> &bull;
  <a href="#support">Support</a> &bull;
  <a href="#license">License</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Odoo-18.0-714B67?style=flat-square&logo=odoo&logoColor=white" alt="Odoo 18"/>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/License-LGPL--3-blue?style=flat-square" alt="LGPL-3"/>
  <img src="https://img.shields.io/badge/LINE-Messaging%20API-00C300?style=flat-square&logo=line&logoColor=white" alt="LINE Messaging API"/>
  <img src="https://img.shields.io/badge/PostgreSQL-13+-336791?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL 13+"/>
</p>

---

## Overview

**woow_odoo_livechat_line** connects LINE Official Accounts to Odoo 18 LiveChat, routing incoming LINE messages into Discuss channels where operators can reply in real time. All media types -- images, video, audio, files, stickers, and locations -- are transferred bidirectionally.

### Why This Module?

| Challenge | Solution |
|-----------|----------|
| LINE customers cannot reach your Odoo helpdesk | Webhook endpoint receives LINE events and creates LiveChat sessions automatically |
| Operators must switch between LINE OA Manager and Odoo | All LINE conversations appear in Odoo Discuss -- one unified inbox |
| No customer identity linking between LINE and Odoo CRM | Automatic `res.partner` creation with `line_user_id`; manual binding wizard available |
| Media files stuck in LINE platform | Images, videos, audio, and documents transfer as Odoo attachments with public access tokens |
| Multiple LINE Official Accounts | Multi-tenant support: each LiveChat channel maps to its own LINE channel credentials |
| Security concerns with webhook endpoints | HMAC-SHA256 signature verification on every incoming request |

---

## Features

### LINE Channel Configuration

- Enable/disable LINE integration per LiveChat channel
- Store LINE Channel ID and Channel Secret securely in Odoo
- Auto-computed webhook URL displayed in channel form
- Validation constraints ensure credentials are present when enabled

### Webhook & Signature Verification

- Public endpoint `/line/webhook/<channel_id>` receives LINE platform callbacks
- HMAC-SHA256 signature verification using the channel secret
- Graceful handling of invalid or disabled channels

### Guest & Contact Management

- Automatic `mail.guest` creation for new LINE users
- LINE Profile API integration fetches `displayName` and `pictureUrl`
- Automatic `res.partner` creation with `line_user_id` field
- SQL unique constraints on `line_user_id` for both `mail.guest` and `res.partner`
- LINE Guest Link Partner Wizard for manual guest-to-partner binding

### Message Types

| Type | LINE to Odoo | Odoo to LINE |
|------|:---:|:---:|
| Text | Supported | Supported |
| Image | Supported | Supported |
| Video | Supported | Supported |
| Audio | Supported | Supported |
| File / Document | Supported | Supported (Flex Message) |
| Sticker | Supported (as text) | -- |
| Location | Supported (as text with Google Maps link) | -- |

### Media Transfer

- Downloads binary content from LINE Content API
- Creates Odoo `ir.attachment` records with proper MIME types
- Generates `access_token` for public URL access
- HTTPS URL enforcement for all media sent to LINE
- Video preview thumbnail generation for outbound video messages
- Flex Message cards for file downloads (styled to match LINE native UI)

### Bidirectional Messaging

- **LINE to Odoo**: Webhook receives events, creates `mail.message` in the discuss channel
- **Odoo to LINE**: `mail.message.create` override detects operator replies and pushes to LINE via Push API
- Context flag `from_line_webhook` prevents message loops
- Batched push: LINE allows max 5 messages per request; module batches automatically

### Multi-Tenant Support

- Each `im_livechat.channel` holds its own LINE credentials
- Token cache keyed by channel ID avoids redundant OAuth calls
- Multiple LINE Official Accounts can coexist on the same Odoo instance

---

## Architecture

```
+------------------+          +------------------+          +------------------+
|                  |          |                  |          |                  |
|   LINE App User  |  <-----> |  LINE Platform   |  <-----> |   Odoo Server    |
|                  |          |                  |          |                  |
+------------------+          +------------------+          +------------------+
                                     |    ^                        |    ^
                                     |    |                        |    |
                              Webhook |    | Push API        Discuss |    | mail.message
                              Events  |    | Messages       Channel |    | create()
                                     v    |                        v    |
                              +------------------+          +------------------+
                              | /line/webhook/   |          | Operator         |
                              | <channel_id>     |  ------> | (Discuss UI)     |
                              +------------------+          +------------------+
```

### Request Flow

```
LINE User sends message
    |
    v
LINE Platform --- POST /line/webhook/<channel_id> ---> Odoo
    |
    +-- Verify X-Line-Signature (HMAC-SHA256)
    +-- Find/create mail.guest (fetch LINE profile)
    +-- Find/create res.partner (auto-link)
    +-- Find/create discuss.channel
    +-- Download media content (if applicable)
    +-- Post mail.message to channel
    |
Operator replies in Discuss
    |
    v
mail.message.create() override
    |
    +-- Detect LINE channel (line_user_id present)
    +-- Build LINE message objects (text, image, video, audio, flex)
    +-- Ensure HTTPS URLs
    +-- Push via LINE Messaging API
    |
    v
LINE User receives reply
```

---

## Module Dependencies

| Module | Purpose |
|--------|---------|
| `im_livechat` | LiveChat channel infrastructure, operator assignment, session management |
| `mail` | `mail.guest`, `mail.message`, `discuss.channel`, attachment handling |

---

## Screenshots

<p align="center">
  <img src="docs/screenshots/livechat_channel_detail.png" alt="LiveChat Channel Detail" width="800"/>
  <br/><em>LiveChat sessions showing LINE conversations with operator assignment</em>
</p>

<p align="center">
  <img src="docs/screenshots/discuss_channel_line_detail.png" alt="LINE Conversation in Discuss" width="800"/>
  <br/><em>LINE conversation in Discuss interface with bidirectional messaging</em>
</p>

<p align="center">
  <img src="docs/screenshots/partner_line_user.png" alt="Partner LINE User ID" width="800"/>
  <br/><em>Partner form showing the LINE User ID field for CRM integration</em>
</p>

<p align="center">
  <img src="docs/screenshots/livechat_sessions_kanban.png" alt="LiveChat Sessions Kanban" width="800"/>
  <br/><em>Session kanban view with LINE entries alongside web LiveChat sessions</em>
</p>

---

## Installation

### Prerequisites

- Odoo 18 Community or Enterprise Edition
- Python 3.10 or higher
- PostgreSQL 13 or higher
- HTTPS endpoint accessible from the internet (required by LINE Messaging API)
- A LINE Official Account with Messaging API enabled

### Steps

1. Clone or copy the module into your Odoo addons directory:

   ```bash
   git clone https://github.com/WOOWTECH/woow_odoo_livechat_line.git \
       /path/to/odoo/addons/woow_odoo_livechat_line
   ```

2. Install the Python dependency (usually already available):

   ```bash
   pip install requests
   ```

3. Restart Odoo and update the module list:

   ```bash
   odoo -u base --stop-after-init
   ```

4. Go to **Apps**, search for **LiveChat LINE Integration**, and click **Install**.

---

## Configuration

### 1. LINE Developer Console

1. Log in to [LINE Developers Console](https://developers.line.biz/console/).
2. Create a **Provider** (or use an existing one).
3. Create a **Messaging API** channel.
4. Note the **Channel ID** and **Channel Secret** from the **Basic settings** tab.
5. Under **Messaging API** tab:
   - Set the **Webhook URL** to:
     ```
     https://your-odoo-domain.com/line/webhook/<livechat_channel_id>
     ```
   - Toggle **Use webhook** to **Enabled**.
   - Toggle **Auto-reply messages** to **Disabled**.
   - Toggle **Greeting messages** to **Disabled** (recommended).
6. The Channel Access Token is obtained automatically via OAuth; no manual token entry is needed.

### 2. Odoo LiveChat Channel

1. Navigate to **LiveChat > Configuration > Channels**.
2. Open (or create) a LiveChat channel.
3. In the **LINE Integration** section:
   - Check **Enable LINE Integration**.
   - Enter the **LINE Channel ID**.
   - Enter the **LINE Channel Secret**.
4. The **Webhook URL** field is auto-computed -- copy it to the LINE Developer Console.
5. Save the channel.
6. Ensure at least one **Operator** is assigned to the channel.

### 3. HTTPS / Reverse Proxy

LINE requires all webhook URLs to use HTTPS. Typical setups:

| Setup | Notes |
|-------|-------|
| Nginx reverse proxy with Let's Encrypt | Recommended for production |
| Cloudflare tunnel | Zero-config HTTPS |
| Odoo.sh | HTTPS provided automatically |
| `proxy_mode = True` in `odoo.conf` | Required when behind a reverse proxy |

Set `web.base.url` to your public HTTPS domain so that media URLs sent to LINE are valid:

```
Settings > Technical > Parameters > System Parameters
Key:   web.base.url
Value: https://your-odoo-domain.com
```

---

## Security

### Permission Model

```
+-------------------------+     +----------------------------+
| im_livechat_group_user  |     | im_livechat_group_manager  |
| (LiveChat Operators)    |     | (LiveChat Managers)        |
+-------------------------+     +----------------------------+
| - Read LINE messages    |     | - All operator permissions |
| - Reply to LINE users   |     | - Configure LINE channels  |
| - Use link wizard       |     | - View Channel Secret      |
+-------------------------+     +----------------------------+
```

### Webhook Security

| Layer | Mechanism |
|-------|-----------|
| Transport | HTTPS required (LINE rejects HTTP webhook URLs) |
| Authentication | HMAC-SHA256 signature verification on every request |
| Authorization | Channel must exist and have `line_enabled = True` |
| Input Validation | Malformed JSON or missing fields are silently rejected |
| XSS Prevention | User-supplied content (location title, address) is escaped via `markupsafe.escape` |

### Data Protection

- LINE Channel Secret is stored in the database (ensure database-level encryption for compliance).
- Access tokens are cached in memory only -- never persisted to disk.
- `line_user_id` fields have SQL unique constraints to prevent data duplication.
- The `access_token` on `ir.attachment` is generated per-attachment for public media URLs.

---

## API Reference

### Webhook Endpoint

```
POST /line/webhook/<int:channel_id>
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `channel_id` | `int` (path) | Odoo `im_livechat.channel` record ID |

**Headers**

| Header | Required | Description |
|--------|----------|-------------|
| `X-Line-Signature` | Yes | HMAC-SHA256 signature of the request body |
| `Content-Type` | Yes | `application/json` |

**Response**: `200 OK` with empty JSON object `{}`. LINE expects a 200 status within 1 second.

### Webhook Events

| Event Type | Handled | Action |
|------------|:---:|--------|
| `message` (text) | Yes | Creates `mail.message` with text body |
| `message` (image) | Yes | Downloads content, creates attachment |
| `message` (video) | Yes | Downloads content, creates attachment |
| `message` (audio) | Yes | Downloads content, creates attachment |
| `message` (file) | Yes | Downloads content, creates attachment |
| `message` (sticker) | Yes | Creates text message `[Sticker: packageId/stickerId]` |
| `message` (location) | Yes | Creates text message with Google Maps link |
| `follow` | Yes | Logged (no action) |
| `unfollow` | Yes | Logged (no action) |
| Other events | No | Logged as debug, silently ignored |

### LINE API Calls (Outbound)

| API | Method | Purpose |
|-----|--------|---------|
| `POST /v2/oauth/accessToken` | OAuth | Obtain channel access token |
| `GET /v2/bot/profile/{userId}` | Profile | Fetch LINE user display name and picture |
| `GET /v2/bot/message/{messageId}/content` | Content | Download media binary |
| `POST /v2/bot/message/push` | Push | Send messages to LINE user |

### Models Reference

| Model | Type | Fields Added |
|-------|------|-------------|
| `im_livechat.channel` | Extended | `line_enabled`, `line_channel_id`, `line_channel_secret`, `line_webhook_url` |
| `discuss.channel` | Extended | `line_user_id`, `line_display_name`, `line_picture_url` |
| `mail.guest` | Extended | `line_user_id`, `line_partner_id` |
| `res.partner` | Extended | `line_user_id` |
| `mail.message` | Extended | `create()` override for outbound LINE push |
| `line.api.mixin` | Abstract | Token cache, push, profile, content, message builders |
| `line.guest.link.partner.wizard` | Transient | `guest_id`, `partner_id`, `action_link()` |

---

## Testing

### Test Summary

| Metric | Value |
|--------|-------|
| Total test methods | **257** |
| Phases 1-5 (core) | 129 |
| Phases 6-13 (production) | 128 |
| Failures | **0** |
| Errors | **0** |

### Test Phases (6-13)

| Phase | File | Tests | Focus |
|-------|------|:---:|-------|
| 6 | `test_phase06_deployment.py` | 17 | Deployment verification, module install, webhook endpoint |
| 7 | `test_phase07_contact_binding.py` | 18 | Guest creation, partner auto-link, wizard binding |
| 8 | `test_phase08_multi_tenant.py` | 14 | Multiple LINE channels, credential isolation |
| 9 | `test_phase09_https_proxy.py` | 14 | HTTPS URL enforcement, proxy mode, base URL handling |
| 10 | `test_phase10_fault_recovery.py` | 16 | API failures, timeout handling, retry logic |
| 11 | `test_phase11_monitoring.py` | 13 | Logging output, error tracking, diagnostics |
| 12 | `test_phase12_data_governance.py` | 18 | Unique constraints, data integrity, access control |
| 13 | `test_phase13_operations.py` | 18 | End-to-end flows, concurrent operations, edge cases |

### Running Tests

```bash
# Run all module tests
odoo --test-enable -i woow_odoo_livechat_line --stop-after-init

# Run a specific test phase
odoo --test-enable -i woow_odoo_livechat_line \
     --test-tags /woow_odoo_livechat_line --stop-after-init
```

---

## Changelog

### 18.0.1.0.0

- Initial release
- LINE Messaging API webhook integration
- Bidirectional text messaging (LINE <-> Odoo Discuss)
- Media transfer: image, video, audio, file (both directions)
- Sticker and location message support (LINE to Odoo)
- Flex Message cards for file downloads (Odoo to LINE)
- Automatic `mail.guest` and `res.partner` creation from LINE profiles
- LINE Guest Link Partner Wizard for manual binding
- HMAC-SHA256 webhook signature verification
- Token cache for LINE Channel Access Tokens
- Multi-tenant support (multiple LINE Official Accounts)
- HTTPS URL enforcement for media access
- 257 automated tests across 13 phases, 0 failures

---

## Support

| Resource | Link |
|----------|------|
| GitHub Issues | [github.com/WOOWTECH/woow_odoo_livechat_line/issues](https://github.com/WOOWTECH/woow_odoo_livechat_line/issues) |
| LINE Developers Documentation | [developers.line.biz/en/docs/messaging-api/](https://developers.line.biz/en/docs/messaging-api/) |
| Odoo LiveChat Documentation | [odoo.com/documentation/18.0/applications/websites/livechat.html](https://www.odoo.com/documentation/18.0/applications/websites/livechat.html) |
| WoowTech | [woowtech.com](https://woowtech.com) |

---

## License

This module is licensed under the [GNU Lesser General Public License v3.0 (LGPL-3)](https://www.gnu.org/licenses/lgpl-3.0.html).

See the [LICENSE](LICENSE) file for the full license text.

---

<p align="center">
  <sub>Built with care by <a href="https://woowtech.com">WoowTech</a> &mdash; Odoo 18 &bull; LINE Messaging API</sub>
</p>
