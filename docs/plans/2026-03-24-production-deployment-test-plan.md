# Production Deployment Test Plan / 商用環境部署測試計畫

# Odoo LINE LiveChat Integration — Production Readiness

**Module:** `woow_odoo_livechat_line`
**Version:** 18.0.1.0.0
**Author:** WoowTech
**Date:** 2026-03-24
**Reference:** [LINE LiveChat PRD](2026-03-24-line-livechat-prd.md)
**Quality Standard:** Commercial Grade (OCA guidelines, automated tests, CI/CD, complete documentation)
**Target Deployment:** Docker/Podman containers → Single customer → SaaS → App Store
**Expected Volume:** Hundreds of messages/day, 3–10 LINE Official Accounts

---

## Scope / 範圍

This document extends the existing PRD with **8 additional test phases (Phase 6–13)** focused on production readiness. Phases 1–5 (core functionality, 129 tests) are documented in the main PRD and have all passed.

| Phase | Area / 領域 | Items / 項目數 |
|-------|-------------|----------------|
| 1–5 | Core Functionality (existing) | 129 |
| **6** | **Deployment & Installation Verification / 部署與安裝驗證** | **16** |
| **7** | **Contact Identification & Binding / 聯絡人辨識與綁定** | **18** |
| **8** | **Multi-tenant / Multi LINE Account / 多租戶與多帳號** | **14** |
| **9** | **HTTPS & Reverse Proxy / HTTPS 與反向代理** | **12** |
| **10** | **High Availability & Fault Recovery / 高可用與故障恢復** | **15** |
| **11** | **Monitoring & Alerting / 監控與告警** | **13** |
| **12** | **Data Governance & Privacy / 資料治理與隱私** | **16** |
| **13** | **Operations Procedures / 營運操作程序** | **15** |
| | **Total New Tests / 新增測試總數** | **119** |
| | **Grand Total / 總計** | **248** |

---

## Phase 6: Deployment & Installation Verification / 部署與安裝驗證

### 6.1 Fresh Installation / 全新安裝

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 6.1.1 | Install module on clean Odoo 18 database | Module installs without error; all dependencies satisfied |
| 6.1.2 | Verify all model fields created | `mail.guest.line_user_id`, `discuss.channel.line_channel_type`, `im_livechat.channel.line_channel_id/secret`, `res.partner.line_user_id` all exist |
| 6.1.3 | Verify XML views loaded | LiveChat channel form, partner form view inherit, guest link wizard all render |
| 6.1.4 | Verify static assets accessible | `/woow_odoo_livechat_line/static/img/video_preview.png` returns 200 |
| 6.1.5 | Verify webhook endpoint registered | `GET /line/webhook` returns 200 (verification); `POST /line/webhook` accepts JSON |

### 6.2 Upgrade from Previous Version / 從舊版升級

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 6.2.1 | Upgrade module with existing LINE conversations | All existing channels, messages, guests preserved |
| 6.2.2 | Upgrade adds `res.partner.line_user_id` field | New column added; existing partners get NULL (no data loss) |
| 6.2.3 | Upgrade adds SQL unique constraints | `mail_guest_line_user_id_unique` and `res_partner_line_user_id_unique` constraints created |
| 6.2.4 | Existing guests without partner get auto-linked on next message | Legacy guest triggers partner creation path |

### 6.3 Configuration Validation / 設定驗證

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 6.3.1 | `web.base.url` set to HTTPS and `web.base.url.freeze = True` | Attachment URLs, video preview URLs all use HTTPS |
| 6.3.2 | LINE Channel ID / Secret saved on LiveChat channel | Fields saved; secret not displayed in plain text in UI |
| 6.3.3 | Webhook URL matches `{web.base.url}/line/webhook` | LINE Developer Console verification succeeds |

### 6.4 Contact Binding on Deploy / 部署後聯絡人綁定

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 6.4.1 | New LINE user → auto `res.partner` creation | First message creates guest + partner with `line_user_id` and `line_display_name` |
| 6.4.2 | Partner form shows LINE User ID field | Field visible after `website` field on partner form |
| 6.4.3 | Manual partner binding via wizard | Wizard links guest to existing partner; `line_user_id` synced to partner |
| 6.4.4 | Duplicate `line_user_id` on partner blocked | Unique constraint prevents two partners with same LINE ID |

---

## Phase 7: Contact Identification & Binding / 聯絡人辨識與綁定

### 7.1 LINE Profile API Integration / LINE Profile API 整合

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 7.1.1 | First message from new LINE user calls Profile API | `GET https://api.line.me/v2/bot/profile/{userId}` called once |
| 7.1.2 | Profile API returns `displayName` → guest name updated | `mail.guest.name` = LINE displayName (not "Visitor #xxx") |
| 7.1.3 | Profile API returns `pictureUrl` → stored on guest | `mail.guest.line_picture_url` populated |
| 7.1.4 | Profile API called only for new/incomplete guests | Second message from same user does NOT call Profile API |
| 7.1.5 | Profile API timeout (> 5 sec) → fallback to "LINE User" | Guest created with generic name; no webhook failure |
| 7.1.6 | Profile API returns 404 (user blocked bot) → graceful handling | Guest created with `line_user_id` as name; warning logged |

### 7.2 Auto Partner Creation / 自動建立聯絡人

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 7.2.1 | New guest → `res.partner` created automatically | Partner has `name` = displayName, `line_user_id` = userId |
| 7.2.2 | Existing guest without partner → partner created on next message | Legacy guests get partner linked retroactively |
| 7.2.3 | Partner `line_user_id` unique constraint enforced | Database prevents duplicate LINE user IDs on partners |
| 7.2.4 | Guest `partner_id` linked to auto-created partner | `mail.guest.partner_id` points to correct `res.partner` |

### 7.3 Manual Binding Wizard / 手動綁定精靈

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 7.3.1 | Open wizard from guest record | Wizard shows guest name, LINE user ID, partner selection |
| 7.3.2 | Link guest to existing partner | `guest.partner_id` updated; `partner.line_user_id` synced |
| 7.3.3 | Link guest to partner that already has different `line_user_id` | Error or confirmation prompt; no silent overwrite |
| 7.3.4 | Unlink guest from partner | `guest.partner_id` cleared; `partner.line_user_id` optionally cleared |

### 7.4 Edge Cases / 邊界情況

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 7.4.1 | LINE user changes displayName | Next message updates guest name (if Profile API re-called) or stays cached |
| 7.4.2 | Two LINE users with identical displayName | Two separate guests + partners; differentiated by `line_user_id` |
| 7.4.3 | LINE userId format validation | Only valid LINE userId format accepted (U[0-9a-f]{32}) |
| 7.4.4 | Partner merge with `line_user_id` conflict | Merge wizard handles or warns about duplicate LINE IDs |

---

## Phase 8: Multi-tenant / Multi LINE Account / 多租戶與多帳號

### 8.1 Multiple LINE Official Accounts / 多個 LINE 官方帳號

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 8.1.1 | Configure 2+ LINE accounts on different LiveChat channels | Each channel has its own `line_channel_id` and `line_channel_secret` |
| 8.1.2 | Webhook routes to correct LiveChat channel | Signature validation per-channel; message routed to matching channel |
| 8.1.3 | Token cache isolation | `_token_cache` keyed by `channel_id`; tokens don't cross-contaminate |
| 8.1.4 | Same LINE user messages two different Official Accounts | Two separate `discuss.channel` records; one guest (same `line_user_id`) |

### 8.2 Multi-company / 多公司

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 8.2.1 | Different LINE accounts per company | Company A and B have independent LINE channel credentials |
| 8.2.2 | Cross-company data isolation | Operators in Company A cannot see Company B's LINE conversations |
| 8.2.3 | `res.partner` with `line_user_id` respects company rules | Partner belongs to creating company; multi-company access rules apply |

### 8.3 Multi-database (SaaS) / 多資料庫（SaaS）

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 8.3.1 | Module installable on multi-database Odoo instance | `--db-filter` routes webhook to correct database |
| 8.3.2 | Webhook URL includes database routing hint | `/line/webhook?db=<dbname>` or path-based routing |
| 8.3.3 | Token cache per-database | Different databases don't share token cache |

### 8.4 Concurrent Load / 並發負載

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 8.4.1 | 10 simultaneous LINE messages → all processed | No lost messages; no duplicate channels |
| 8.4.2 | Same user sends 5 rapid messages | All 5 messages in same channel; no race condition creating duplicates |
| 8.4.3 | 50 concurrent webhook POSTs | Server responds to all within LINE's timeout (< 1 min per spec) |
| 8.4.4 | Token refresh under concurrent load | Only one refresh call; others wait or use cached token |

---

## Phase 9: HTTPS & Reverse Proxy / HTTPS 與反向代理

### 9.1 TLS Configuration / TLS 設定

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 9.1.1 | Webhook endpoint only accessible via HTTPS | HTTP → 301 redirect to HTTPS; LINE webhook only sends to HTTPS |
| 9.1.2 | TLS certificate valid and not self-signed | LINE Platform validates cert; webhook verification succeeds |
| 9.1.3 | TLS 1.2+ enforced | SSLv3, TLS 1.0, TLS 1.1 disabled |
| 9.1.4 | Certificate auto-renewal (Let's Encrypt / Cloudflare) | Cert renews before expiry; no manual intervention needed |

### 9.2 Reverse Proxy Headers / 反向代理標頭

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 9.2.1 | `X-Forwarded-Proto: https` passed to Odoo | Odoo generates HTTPS URLs for attachments and preview images |
| 9.2.2 | `X-Forwarded-Host` matches `web.base.url` | No URL mismatch between Odoo-generated URLs and actual domain |
| 9.2.3 | `--proxy-mode` enabled on Odoo | Odoo trusts proxy headers; correct client IP logged |

### 9.3 Attachment URL Accessibility / 附件 URL 可存取性

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 9.3.1 | Image attachment URL accessible from LINE Platform | LINE can fetch image for display in chat (via `originalContentUrl`) |
| 9.3.2 | Video attachment URL supports Range requests | `HTTP 206 Partial Content` for video streaming |
| 9.3.3 | `video_preview.png` accessible via HTTPS | `{base_url}/woow_odoo_livechat_line/static/img/video_preview.png` returns 200 |
| 9.3.4 | Attachment access tokens not enumerable | Random tokens; sequential guessing yields 403 |
| 9.3.5 | Large file upload through proxy (> 25 MB) | Nginx `client_max_body_size` configured; Odoo receives complete file |

---

## Phase 10: High Availability & Fault Recovery / 高可用與故障恢復

### 10.1 Container Lifecycle / 容器生命週期

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 10.1.1 | Container restart preserves conversations | `podman restart` → all channels, messages intact |
| 10.1.2 | Container crash auto-recovery | `--restart=always` policy; container restarts within 30 sec |
| 10.1.3 | Graceful shutdown during message processing | Active webhook request completes or returns 500 (LINE retries) |
| 10.1.4 | Container image rebuild and redeploy | New image with module update; volume-mounted filestore preserved |

### 10.2 Database Resilience / 資料庫韌性

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 10.2.1 | PostgreSQL connection pool exhaustion | Odoo returns 500; LINE retries; recovers when connections freed |
| 10.2.2 | Database backup during active conversations | `pg_dump` doesn't block webhook processing (MVCC) |
| 10.2.3 | Point-in-time recovery | Restore to specific timestamp; messages after that point re-deliverable by LINE |

### 10.3 External Service Failures / 外部服務故障

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 10.3.1 | LINE Push API returns 429 (rate limited) | Retry with exponential backoff; message eventually delivered |
| 10.3.2 | LINE Push API returns 500 (server error) | Retry up to 3 times; log error; operator sees warning |
| 10.3.3 | LINE Content API timeout during media download | Attachment created with error note; retry mechanism or manual re-fetch |
| 10.3.4 | DNS resolution failure | Logged; operator notified; auto-recovery when DNS restored |

### 10.4 Data Integrity / 資料完整性

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 10.4.1 | Unique constraint on `mail.guest.line_user_id` | Race condition creating duplicate guests → DB constraint prevents it |
| 10.4.2 | Unique constraint on `res.partner.line_user_id` | Concurrent partner creation → only one succeeds; other links to existing |
| 10.4.3 | Orphan channel cleanup | Channels with no messages after 24h flagged for review |
| 10.4.4 | Attachment without linked message | Cron or manual cleanup for orphan attachments |
| 10.4.5 | Transaction rollback on partial failure | Webhook processing is atomic; partial message+attachment not committed |

---

## Phase 11: Monitoring & Alerting / 監控與告警

### 11.1 Application Metrics / 應用程式指標

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 11.1.1 | Webhook request count logged | `_logger.info` includes channel, user, message type per request |
| 11.1.2 | Webhook processing time measurable | Log entry includes duration; > 5s triggers warning |
| 11.1.3 | LINE API call success/failure rate | Push/Content/Profile API calls logged with HTTP status |
| 11.1.4 | Token refresh events logged | Cache miss → refresh logged with channel_id and success/failure |

### 11.2 Infrastructure Monitoring / 基礎設施監控

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 11.2.1 | Container health check endpoint | `/web/health` returns 200; container orchestrator monitors it |
| 11.2.2 | Odoo worker process count | `--workers` configured; all workers responsive |
| 11.2.3 | Database connection pool utilization | `db_maxconn` not exhausted under normal load |
| 11.2.4 | Disk usage for filestore | Alert at 80% capacity; attachments are primary growth driver |

### 11.3 Alerting Rules / 告警規則

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 11.3.1 | Webhook returns 500 more than 5 times in 1 minute | Alert to ops team (email/Slack/LINE) |
| 11.3.2 | No webhook activity for > 1 hour during business hours | Alert: possible webhook URL misconfiguration or LINE platform issue |
| 11.3.3 | LINE Push API failure rate > 10% | Alert: possible token expiry or API quota exceeded |
| 11.3.4 | Container restart detected | Alert: investigate crash cause in logs |
| 11.3.5 | SSL certificate expiry within 14 days | Alert: renew certificate or check auto-renewal |

---

## Phase 12: Data Governance & Privacy / 資料治理與隱私

### 12.1 Personal Data Inventory / 個人資料盤點

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 12.1.1 | Audit all LINE user PII stored in database | `line_user_id`, `line_display_name`, `line_picture_url` on `mail.guest`, `discuss.channel`, `res.partner` identified and documented |
| 12.1.2 | Verify no LINE `accessToken` persisted to database | Token only in `_token_cache` (memory); no DB columns store credentials |
| 12.1.3 | Verify LINE `channel_secret` stored in encrypted/restricted field | Field on `im_livechat.channel` accessible only to LiveChat admin group |

### 12.2 Data Retention & Deletion / 資料保留與刪除

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 12.2.1 | Define conversation retention policy | Configurable retention period (e.g., 90/180/365 days) or "indefinite" |
| 12.2.2 | Delete a LINE guest record | Related `discuss.channel`, `mail.message`, `ir.attachment` cascade handled; no orphan records |
| 12.2.3 | Delete a linked `res.partner` with `line_user_id` | Partner deleted; guest `partner_id` nullified; LINE conversations preserved for audit |
| 12.2.4 | Verify attachment binary cleanup | Deleted `ir.attachment` records have filestore binaries garbage-collected |
| 12.2.5 | Export user data on request (data portability) | All messages, attachments, and profile data for a given `line_user_id` exportable as JSON/ZIP |

### 12.3 Consent & Transparency / 同意與透明

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 12.3.1 | LINE Official Account rich menu includes privacy notice link | Users can access privacy policy before/during conversation |
| 12.3.2 | First-message welcome includes data collection notice | Auto-reply or greeting mentions data collection purpose |
| 12.3.3 | LINE user "unfollow" event triggers data handling | `unfollow` event logged; operator notified; optional: auto-close active channels |

### 12.4 Access Control / 存取控制

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 12.4.1 | Non-admin user cannot view LINE credentials | `line_channel_id`, `line_channel_secret` fields restricted to LiveChat Manager group |
| 12.4.2 | Operator can only see own assigned conversations | Standard Odoo Discuss ACL applies; operators don't see other operators' LINE channels |
| 12.4.3 | Guest records not exposed via public API | `/web/dataset/call_kw` for `mail.guest` requires authentication |
| 12.4.4 | Attachment `access_token` not predictable | Tokens generated via `generate_access_token()` are cryptographically random |

### 12.5 Audit Trail / 稽核軌跡

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 12.5.1 | All inbound LINE messages logged with timestamp | `mail.message` records include `create_date`, `author_guest_id`, source channel |
| 12.5.2 | All outbound LINE messages logged | Push API calls logged in Odoo logger with message type and target user |
| 12.5.3 | Partner binding actions logged | Guest-to-partner linking creates `mail.tracking.value` or chatter entry on partner |

---

## Phase 13: Operations Procedures / 營運操作程序

### 13.1 Module Upgrade & Migration / 模組升級與遷移

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 13.1.1 | `--update woow_odoo_livechat_line` completes without error | Module upgrade applies new migrations; existing data preserved |
| 13.1.2 | Database migration scripts handle schema changes | New fields/constraints added gracefully; no data loss on upgrade |
| 13.1.3 | Rollback to previous module version | Downgrade path documented; if not supported, clearly stated with backup procedure |
| 13.1.4 | Odoo minor version upgrade (e.g., 18.0.1 → 18.0.2) | Module remains compatible; no import errors or view breakage |

### 13.2 LINE Account Lifecycle / LINE 帳號生命週期

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 13.2.1 | LINE Channel Token expiry and refresh | Token cache invalidation triggers re-auth; no message loss during refresh window |
| 13.2.2 | LINE Official Account plan downgrade | Reduced messaging quota respected; excess messages queued or operator warned |
| 13.2.3 | LINE Channel credential rotation | Update `channel_secret` / `channel_id` in Odoo; webhook continues after re-verification |
| 13.2.4 | LINE webhook URL change | Update URL in LINE Developer Console; old URL returns 404; new URL processes immediately |

### 13.3 Incident Response / 事件應變

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 13.3.1 | LINE Platform outage (5xx from API) | Outbound messages retry with backoff; inbound webhook returns 200 to LINE (avoid redelivery storm) |
| 13.3.2 | Odoo database connection lost | Webhook returns 500; LINE retries; messages recovered after DB reconnect |
| 13.3.3 | Container OOM kill | Container auto-restarts (`--restart=always`); active conversations resumable |
| 13.3.4 | Disk full — attachment storage | Graceful error message to operator; LINE user sees retry prompt; alert fired |

### 13.4 Backup & Restore / 備份與還原

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 13.4.1 | Full database backup includes LINE data | `pg_dump` captures `mail.guest.line_user_id`, `res.partner.line_user_id`, all conversations |
| 13.4.2 | Filestore backup includes LINE attachments | Images, videos, audio, documents all present in filestore backup |
| 13.4.3 | Restore to new server | Restored instance resumes LINE webhook processing after DNS/URL update |

### 13.5 Capacity Planning / 容量規劃

| # | Test Item / 測試項目 | Expected Result / 預期結果 |
|---|----------------------|---------------------------|
| 13.5.1 | Estimate storage growth per 1,000 conversations | Documented: avg message size, attachment ratio, DB + filestore growth projection |
| 13.5.2 | LINE Messaging API rate limits documented | Free: 500/month, Light: 5,000, Standard: 25,000, Pro: unlimited push; documented with alerting thresholds |
| 13.5.3 | Database connection pool sizing | Odoo `db_maxconn` configured for concurrent webhook + operator load |

---

## Summary / 摘要

| Phase | Area / 領域 | Test Items / 測試項目數 | Status / 狀態 |
|-------|-------------|------------------------|---------------|
| 1–5 | Core Functionality / 核心功能 | 129 | ✅ PASSED |
| 6 | Deployment & Installation / 部署與安裝 | 16 | ⬜ Pending |
| 7 | Contact Identification & Binding / 聯絡人辨識與綁定 | 18 | ⬜ Pending |
| 8 | Multi-tenant / Multi LINE Account / 多租戶與多帳號 | 14 | ⬜ Pending |
| 9 | HTTPS & Reverse Proxy / HTTPS 與反向代理 | 12 | ⬜ Pending |
| 10 | High Availability & Fault Recovery / 高可用與故障恢復 | 15 | ⬜ Pending |
| 11 | Monitoring & Alerting / 監控與告警 | 13 | ⬜ Pending |
| 12 | Data Governance & Privacy / 資料治理與隱私 | 16 | ⬜ Pending |
| 13 | Operations Procedures / 營運操作程序 | 15 | ⬜ Pending |
| | **Grand Total / 總計** | **248** | |

---

*Generated on 2026-03-24 by WoowTech AI Coder*
