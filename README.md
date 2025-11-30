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
| 🔍 **Smart Filters** | Filter by age, size, and category (Promotions, Social, Updates) |
| 🔒 **Privacy First** | Runs locally - your data never leaves your machine |
| ⚡ **Super Fast** | Gmail API with batch requests (100 emails per API call) |
| 🎨 **Gmail-style UI** | Clean, familiar interface |

## Demo

![Gmail Cleaner Demo](demo.gif)

*Filter by age/size/category → Scan senders → Select → Delete thousands of emails in seconds!*

## Setup

> ⚠️ **Important**: You must create your **OWN** Google Cloud credentials.  
> This app doesn't include pre-configured OAuth - that's what makes it privacy-focused!  
> Each user runs their own instance with their own credentials.

### 1. Get Google OAuth Credentials

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
   - Rename to `credentials.json`

### 2. Clone the Repository

```bash
git clone https://github.com/Gururagavendra/gmail-cleaner.git
cd gmail-cleaner
```

Put your `credentials.json` file in the project folder.

## Usage

### Option A: Docker (Recommended)

```bash
docker compose up -d
```

Open http://localhost:8766 in your browser.

**First-time sign-in:** Click "Sign In" in the web UI, then check logs for the OAuth URL:
```bash
docker logs cleanup_email-gmail-cleaner-1
```

Copy the URL from logs, open in browser, and authorize.

### Option B: Python (with uv)

```bash
uv sync
uv run python main.py
```

The app opens at http://localhost:8766

## Security & Privacy

- ✅ **100% Local** - No external servers, no data collection
- ✅ **Open Source** - Inspect all the code yourself
- ✅ **Minimal Permissions** - Only requests read + modify (for mark as read)
- ✅ **Your Credentials** - You control your own Google OAuth app
- ✅ **Gitignored Secrets** - `credentials.json` and `token.json` never get committed

## FAQ

**Q: Why do I need to create my own Google Cloud project?**
> Because this app accesses your Gmail. By using your own OAuth credentials, you have full control and don't need to trust a third party.

**Q: Is this safe?**
> Yes! The code is open source - you can inspect it. Your emails are processed locally on your machine.

**Q: Can I use this for multiple Gmail accounts?**
> Yes! Click "Sign Out" and sign in with a different account. Each account needs to be added as a test user in your Google Cloud project.

**Q: Emails went to Trash, can I recover them?**
> Yes! The delete feature moves emails to Trash. Go to Gmail → Trash to recover within 30 days.

## Troubleshooting

### "Access blocked: Gmail Cleanup has not completed the Google verification process"

This error means you're missing a step in the OAuth setup:

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → Your Project
2. Go to **APIs & Services** → **OAuth consent screen**
3. Scroll down to **Test users**
4. Click **Add Users** and add your Gmail address
5. Try signing in again

> 💡 **Why?** Since your app is in "Testing" mode, only emails listed as test users can sign in. This is normal and expected!

### "Error 403: access_denied"

- Make sure you created your **own** Google Cloud project and credentials
- Make sure your email is added as a **Test user**
- Make sure you downloaded `credentials.json` and placed it in the project folder

### Docker: "Where do I find the OAuth URL?"

Check the container logs:
```bash
docker logs cleanup_email-gmail-cleaner-1
```
Look for a URL starting with `https://accounts.google.com/o/oauth2/...`

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
