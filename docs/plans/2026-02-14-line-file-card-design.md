# LINE File Card Design - PRD

## Problem Statement

需要讓 Odoo 發送到 LINE 的檔案訊息樣式與官方 LINE 檔案卡片一致。

## Analysis of Official LINE File Card (from screenshot)

### Visual Elements

1. **Overall Container**
   - 圓角白色卡片
   - 有微妙的陰影/邊框
   - 緊湊的尺寸

2. **Left Icon Area**
   - **深藍灰色背景** (約 #5B6B7C 或類似)
   - **白色折角文件圖示**
   - 正方形，約 40-45px
   - 小圓角

3. **Right Text Area**
   - **檔案名稱**: 黑色，正常字重，可能被截斷
   - **檔案大小**: 灰色，較小字體
   - 垂直居中對齊

4. **Interaction**
   - 整個卡片可點擊
   - 點擊後下載/開啟檔案

## Technical Constraints

根據 [LINE Message Types](https://developers.line.biz/en/docs/messaging-api/message-types/):
- LINE Messaging API **不支援**原生的檔案訊息發送
- 只支援: text, image, video, audio, location, sticker, template, flex
- 必須使用 **Flex Message** 來模擬檔案卡片

## Design Solution

使用 Flex Message 的 `bubble` 容器，模擬官方樣式：

```json
{
  "type": "flex",
  "altText": "檔案名稱",
  "contents": {
    "type": "bubble",
    "size": "nano",
    "body": {
      "type": "box",
      "layout": "horizontal",
      "contents": [
        {
          "type": "box",
          "layout": "vertical",
          "contents": [
            {
              "type": "image",
              "url": "[FILE_ICON_URL]",
              "size": "full",
              "aspectMode": "fit"
            }
          ],
          "width": "45px",
          "height": "45px",
          "backgroundColor": "#5B6B7C",
          "cornerRadius": "6px",
          "justifyContent": "center",
          "alignItems": "center"
        },
        {
          "type": "box",
          "layout": "vertical",
          "contents": [
            {
              "type": "text",
              "text": "filename.pdf",
              "size": "sm",
              "color": "#111111",
              "wrap": false
            },
            {
              "type": "text",
              "text": "1.2 MB",
              "size": "xs",
              "color": "#8C8C8C"
            }
          ],
          "margin": "md",
          "justifyContent": "center"
        }
      ],
      "paddingAll": "md",
      "action": {
        "type": "uri",
        "uri": "https://download-url"
      }
    }
  }
}
```

## Key Design Decisions

1. **Bubble Size**: 使用 `nano` 讓卡片更緊湊
2. **Icon Background**: `#5B6B7C` (深藍灰色，接近官方)
3. **File Icon**: 由於無法使用官方圖示，使用白色文字顯示副檔名
4. **整體可點擊**: 使用 `action` 在 body 層級

## Implementation

更新 `models/line_api.py` 中的 `_line_build_file_message()` 方法。

## References

- [LINE Flex Message Elements](https://developers.line.biz/en/docs/messaging-api/flex-message-elements/)
- [LINE Flex Message Layout](https://developers.line.biz/en/docs/messaging-api/flex-message-layout/)
- [LINE Flex Message Simulator](https://developers.line.biz/flex-simulator/)
