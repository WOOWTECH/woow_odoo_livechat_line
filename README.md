# Odoo LINE LiveChat Integration

Integrate LINE Messaging API with Odoo 18 Community LiveChat module, enabling seamless bidirectional communication between LINE users and Odoo operators.

[繁體中文](README_zh-TW.md)

## Features

- **Bidirectional Messaging**: Send and receive messages between LINE and Odoo LiveChat
- **Media Support**:
  - LINE to Odoo: Images, videos, audio files, and documents
  - Odoo to LINE: Images, videos, audio files, and documents (with Flex Message card)
- **Real-time Communication**: Instant message delivery via LINE webhook
- **Guest Integration**: LINE users appear as guests in Odoo Discuss
- **Operator Reply**: Odoo operators can reply directly from LiveChat interface

## Requirements

- Odoo 18 Community Edition
- LINE Messaging API Channel (LINE Official Account)
- HTTPS endpoint for webhook (required by LINE)

## Installation

1. Clone this module to your Odoo addons directory:
   ```bash
   git clone https://github.com/WOOWTECH/woow_odoo_livechat_line.git
   ```

2. Update Odoo module list and install `woow_odoo_livechat_line`

3. Configure LINE channel settings in LiveChat configuration

## Configuration

### LINE Developer Console

1. Create a LINE Messaging API channel at [LINE Developers](https://developers.line.biz/)
2. Get your **Channel ID** and **Channel Secret**
3. Set webhook URL to: `https://your-odoo-domain/line/webhook/<livechat_channel_id>`
4. Enable webhook and disable auto-reply messages

### Odoo Configuration

1. Go to **LiveChat > Configuration > Channels**
2. Edit your LiveChat channel
3. Enable **LINE Integration**
4. Enter your LINE **Channel ID** and **Channel Secret**
5. Save

## Message Types Support

| Type | LINE to Odoo | Odoo to LINE |
|------|-------------|-------------|
| Text | Supported | Supported |
| Image | Supported | Supported |
| Video | Supported | Supported |
| Audio | Supported | Supported |
| File/Document | Supported | Supported (Flex Message) |
| Sticker | Supported (as text) | Not supported |
| Location | Supported (as text) | Not supported |

## Architecture

```
LINE User                    Odoo
    |                          |
    |---- Message ------------>| Webhook Controller
    |                          |      |
    |                          |      v
    |                          | discuss.channel
    |                          |      |
    |                          |      v
    |                          | mail.message
    |                          |      |
    |<--- Reply ---------------|LINE API Mixin
    |                          |
```

## File Structure

```
woow_odoo_livechat_line/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── webhook.py          # LINE webhook handler
├── models/
│   ├── __init__.py
│   ├── discuss_channel.py  # Channel with LINE user association
│   ├── im_livechat_channel.py  # LiveChat LINE configuration
│   ├── line_api.py         # LINE API methods mixin
│   └── mail_message.py     # Message hook for LINE replies
├── views/
│   └── im_livechat_channel_views.xml
├── security/
│   └── ir.model.access.csv
└── README.md
```

## Troubleshooting

### Messages not appearing in Odoo
- Check webhook URL is correctly configured in LINE Developer Console
- Verify HTTPS certificate is valid
- Check Odoo logs for webhook errors

### Media files not transferring
- Ensure `access_token` is generated for attachments
- Verify HTTPS URLs are accessible publicly

### Flex Message showing as JSON
- This is a known LINE limitation for older app versions
- Update LINE app to latest version

## License

LGPL-3.0

## Author

WOOWTECH

## Links

- [GitHub Repository](https://github.com/WOOWTECH/woow_odoo_livechat_line)
- [LINE Developers](https://developers.line.biz/)
- [LINE Messaging API Documentation](https://developers.line.biz/en/docs/messaging-api/)
