# Odoo 18 LiveChat LINE 整合模組 - 實作計畫

## Goal
建立 `woow_odoo_livechat_line` 模組，整合 LINE Messaging API 與 Odoo 18 Community LiveChat。

## Phases

### Phase 1: 基礎模組結構 `in_progress`
- [ ] 建立 `__manifest__.py`
- [ ] 建立 `__init__.py` 檔案結構
- [ ] 建立基本目錄結構

### Phase 2: 資料模型 `pending`
- [ ] 擴展 `im_livechat.channel` - 新增 LINE 設定欄位
- [ ] 擴展 `discuss.channel` - 新增 LINE 用戶關聯欄位
- [ ] 擴展 `mail.guest` - 新增 LINE User ID 欄位

### Phase 3: 前端介面 `pending`
- [ ] 建立 LiveChat 頻道設定的 LINE 分頁

### Phase 4: Webhook Controller `pending`
- [ ] 建立 `/line/webhook/<channel_id>` 端點
- [ ] 實作 LINE 簽章驗證
- [ ] 處理 LINE 訊息事件

### Phase 5: 訊息接收流程 `pending`
- [ ] 查找或建立 mail.guest
- [ ] 查找或建立 discuss.channel
- [ ] 建立 mail.message

### Phase 6: 訊息回覆流程 `pending`
- [ ] Override mail.message create 方法
- [ ] 呼叫 LINE Messaging API 發送訊息

### Phase 7: 訪客關聯聯絡人 `pending`
- [ ] 實作客服手動關聯 Partner 功能

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| - | - | - |

## Files Created/Modified
- task_plan.md
- findings.md
- progress.md
