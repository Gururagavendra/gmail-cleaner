# 📧 Gmail Bulk Unsubscribe & Cleanup Tool

A **free**, privacy-focused tool to bulk unsubscribe from emails, delete emails by sender, and mark emails as read. No subscriptions, no data collection - runs 100% on your machine.

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker)
![Gmail API](https://img.shields.io/badge/Gmail-API-EA4335?style=flat-square&logo=gmail)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

> ✨ **No Subscription Required - Free Forever**

## Features

| Feature | Description |
|---------|-------------|
| 🚫 **Bulk Unsubscribe** | Find newsletters and unsubscribe with one click |
| 🗑️ **Delete by Sender** | See who sends you the most emails, delete in bulk |
| ✅ **Mark as Read** | Bulk mark thousands of unread emails as read |
| 🔒 **Privacy First** | Runs locally - your data never leaves your machine |
| ⚡ **Super Fast** | Gmail API with batch requests (100 emails per API call) |
| 🎨 **Gmail-style UI** | Clean, familiar interface |

## Demo

![Gmail Cleaner Demo](demo.gif)

*Scan senders → Select → Delete thousands of emails in seconds!*

## Prerequisites

- [Google Cloud Project](https://console.cloud.google.com/) with Gmail API enabled
- \`credentials.json\` file (OAuth 2.0 Client ID)
- Docker **OR** Python 3.9+

## Installation

### 1. Get Google OAuth Credentials (one-time setup)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Search for **"Gmail API"** and **Enable** it
4. Go to **APIs & Services** → **OAuth consent screen**
   - Choose **External**
   - Fill in App name: "Gmail Cleanup" (or anything)
   - Add your email as **Test user**
5. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
   - Application type: **Desktop app**
   - Download the JSON file
   - Rename to \`credentials.json\`

### 2. Clone the Repository

\`\`\`bash
git clone https://github.com/Gururagavendra/gmail-cleaner.git
cd gmail-cleaner
\`\`\`

Put your \`credentials.json\` file in the project folder.

## Usage

### Docker (Recommended)

\`\`\`bash
docker compose up -d
\`\`\`

Open http://localhost:8766 in your browser.

**First-time sign-in:**
\`\`\`bash
# Click "Sign In" in the web UI, then check logs for OAuth URL:
docker logs cleanup_email-gmail-cleaner-1
\`\`\`

Copy the URL from logs, open in browser, and authorize.

### Python (with uv)

\`\`\`bash
uv sync
uv run python main.py
\`\`\`

### Python (with pip)

\`\`\`bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install google-auth google-auth-oauthlib google-api-python-client
python main.py
\`\`\`

The app opens at http://localhost:8766

## Docker Configuration

The Docker setup exposes two ports:
- **8766**: Web UI
- **8767**: OAuth callback (for authentication)

\`\`\`yaml
services:
  gmail-cleaner:
    build: .
    ports:
      - "8766:8766"
      - "8767:8767"
    volumes:
      - ./credentials.json:/app/credentials.json:ro
      - ./token.json:/app/token.json  # Persists login
\`\`\`

## Project Structure

\`\`\`
gmail-cleaner/
├── main.py              # Entry point
├── server.py            # HTTP server
├── gmail_api.py         # Gmail API functions
├── pyproject.toml       # Python dependencies
├── Dockerfile
├── docker-compose.yml
├── templates/
│   └── index.html
├── static/
│   ├── styles.css
│   └── script.js
├── credentials.json     # Your OAuth creds (not in git)
└── token.json           # Auth token (not in git)
\`\`\`

## Security & Privacy

- ✅ **100% Local** - No external servers, no data collection
- ✅ **Open Source** - Inspect all the code yourself
- ✅ **Minimal Permissions** - Only requests read + modify (for mark as read)
- ✅ **Your Credentials** - You control your own Google OAuth app
- ✅ **Gitignored Secrets** - \`credentials.json\` and \`token.json\` never get committed

## FAQ

**Q: Why do I need to create my own Google Cloud project?**
> Because this app accesses your Gmail. By using your own OAuth credentials, you have full control and don't need to trust a third party.

**Q: Is this safe?**
> Yes! The code is open source - you can inspect it. Your emails are processed locally on your machine.

**Q: Can I use this for multiple Gmail accounts?**
> Yes! Click "Sign Out" and sign in with a different account. Each account needs to be added as a test user in your Google Cloud project.

**Q: Emails went to Trash, can I recover them?**
> Yes! The delete feature moves emails to Trash. Go to Gmail → Trash to recover within 30 days.

## Tech Stack

- **Backend**: Python 3.11, Gmail API
- **Frontend**: Vanilla HTML/CSS/JS (no frameworks)
- **Auth**: Google OAuth 2.0
- **Package Manager**: uv
- **Containerization**: Docker

## Contributing

PRs welcome! Feel free to:
- Report bugs
- Suggest features
- Improve the UI
- Add new functionality

## License

MIT License - Use it however you want!

---

<p align="center">
  Made with ❤️ to help you escape email hell
</p>
