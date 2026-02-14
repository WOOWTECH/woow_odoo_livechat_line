# LINE Media Transfer Fix - Design Document

## Problem Statement

Odoo 發送到 LINE 的檔案訊息格式顯示不正確。LINE 應用程式顯示原始 JSON 結構（如 `type: bubble, size: kilo`）而不是正確渲染的訊息。

## Root Cause Analysis

根據 LINE 官方文件和程式碼分析：

1. **Flex Message 格式問題**：我們使用的 Flex Message 格式可能不被 LINE 正確解析
2. **訊息類型限制**：LINE 原生只支援 text, image, video, audio, location, sticker 等訊息類型，不支援原生的「檔案」訊息
3. **URL 要求**：所有媒體 URL 必須是 HTTPS 且公開可存取

## LINE Message Types (Official)

根據 [LINE Developers 文件](https://developers.line.biz/en/docs/messaging-api/message-types/)：

| Type | Required Fields | Notes |
|------|-----------------|-------|
| text | type, text | 最多 5000 字元 |
| image | type, originalContentUrl, previewImageUrl | HTTPS, JPEG/PNG, max 10MB |
| video | type, originalContentUrl, previewImageUrl | HTTPS, MP4, max 200MB |
| audio | type, originalContentUrl, duration | HTTPS, M4A, max 200MB |
| flex | type, altText, contents | 自訂版面配置 |

## Solution Options

### Option 1: Use Text Message with Download Link (Recommended)

**優點**：
- 簡單可靠
- 所有 LINE 版本都支援
- 不需要複雜的 Flex Message 結構

**實作**：
```python
def _line_build_file_message(self, filename, file_url, file_size=None):
    size_text = ''
    if file_size:
        size_text = f' ({self._format_file_size(file_size)})'
    return {
        'type': 'text',
        'text': f'📎 {filename}{size_text}\n{file_url}'
    }
```

### Option 2: Fix Flex Message Format

**優點**：
- 更美觀的 UI
- 可點擊的下載按鈕

**缺點**：
- 複雜度高
- 需要驗證 Flex Message 結構是否正確
- 舊版 LINE 可能不支援

### Option 3: Use Image as File Preview

對於圖片和可預覽的檔案，直接使用 image message。

## Recommendation

採用 **Option 1** - 使用純文字訊息加下載連結。

原因：
1. 程式碼已經實作了這個方案（`discuss_channel.py` 第 117-136 行）
2. 最簡單可靠的方案
3. 截圖中的問題可能是舊程式碼（部署前）的結果

## Implementation Checklist

- [x] 修改 `discuss_channel.py` 使用文字訊息格式發送檔案
- [ ] 確認 Odoo 重啟後程式碼生效
- [ ] 測試 Odoo → LINE 檔案發送
- [ ] 驗證 LINE → Odoo 媒體接收
- [ ] 清理 `line_api.py` 中未使用的 Flex Message 方法

## Media Format Support Matrix

| Direction | Type | Format | Status |
|-----------|------|--------|--------|
| LINE → Odoo | Image | JPEG/PNG/GIF | ✅ Working |
| LINE → Odoo | Video | MP4 | ✅ Working |
| LINE → Odoo | Audio | M4A/AAC | ✅ Working |
| LINE → Odoo | File | Any | ✅ Working |
| Odoo → LINE | Image | JPEG/PNG | 🔄 Testing |
| Odoo → LINE | Video | MP4 | 🔄 Testing |
| Odoo → LINE | Audio | M4A | 🔄 Testing |
| Odoo → LINE | File | Any (text link) | 🔄 Testing |

## Next Steps

1. 請使用者從 Odoo 發送一個新的檔案到 LINE 測試
2. 檢查是否正確顯示為文字連結格式
3. 確認連結可以正常下載

## References

- [LINE Message Types](https://developers.line.biz/en/docs/messaging-api/message-types/)
- [LINE Flex Messages](https://developers.line.biz/en/docs/messaging-api/using-flex-messages/)
- [LINE Push Message API](https://developers.line.biz/en/docs/messaging-api/sending-messages/)
