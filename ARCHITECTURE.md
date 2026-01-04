# OAuth Flow & Gmail Cleaner Architecture Guide

This document explains how OAuth 2.0 works and how the Gmail Cleaner application uses it to access your Gmail.

## Table of Contents
1. [OAuth 2.0 Flow Explained](#oauth-20-flow-explained)
2. [How Gmail Cleaner Uses OAuth](#how-gmail-cleaner-uses-oauth)
3. [Application Architecture](#application-architecture)
4. [Gmail API Operations](#gmail-api-operations)
5. [Code Walkthrough](#code-walkthrough)

---

## OAuth 2.0 Flow Explained

### What is OAuth 2.0?

OAuth 2.0 is an **authorization framework** that allows applications to access user data (like Gmail) **without** storing the user's password. Instead, the user grants permission through Google's secure login page.

### The OAuth 2.0 Flow (Step by Step)

```
┌─────────┐         ┌──────────┐         ┌──────────┐         ┌─────────┐
│  User   │         │  App     │         │  Google  │         │  Gmail  │
│ Browser │         │ (Server) │         │  OAuth   │         │   API   │
└────┬────┘         └────┬─────┘         └────┬─────┘         └────┬────┘
     │                   │                    │                    │
     │ 1. Click "Sign In" │                    │                    │
     │──────────────────>│                    │                    │
     │                   │                    │                    │
     │                   │ 2. Create OAuth URL │                    │
     │                   │    (with client_id,│                    │
     │                   │     redirect_uri,   │                    │
     │                   │     scopes)         │                    │
     │                   │                    │                    │
     │                   │ 3. Get auth URL    │                    │
     │                   │<───────────────────│                    │
     │                   │                    │                    │
     │ 4. Redirect to     │                    │                    │
     │    Google Login    │                    │                    │
     │<───────────────────                    │                    │
     │                   │                    │                    │
     │ 5. User logs in &  │                    │                    │
     │    grants access   │                    │                    │
     │───────────────────────────────────────>│                    │
     │                   │                    │                    │
     │                   │                    │ 6. Google generates │
     │                   │                    │    authorization    │
     │                   │                    │    code             │
     │                   │                    │                    │
     │ 7. Redirect with   │                    │                    │
     │    code            │                    │                    │
     │<───────────────────────────────────────│                    │
     │                   │                    │                    │
     │ 8. Send code to    │                    │                    │
     │    callback URL    │                    │                    │
     │──────────────────>│                    │                    │
     │                   │                    │                    │
     │                   │ 9. Exchange code    │                    │
     │                   │    for tokens       │                    │
     │                   │───────────────────>│                    │
     │                   │                    │                    │
     │                   │ 10. Receive tokens  │                    │
     │                   │     (access_token,  │                    │
     │                   │      refresh_token) │                    │
     │                   │<────────────────────│                    │
     │                   │                    │                    │
     │                   │ 11. Save tokens    │                    │
     │                   │     to token.json   │                    │
     │                   │                    │                    │
     │                   │ 12. Use access_token│                    │
     │                   │     to call Gmail   │                    │
     │                   │     API            │                    │
     │                   │─────────────────────────────────────────>│
     │                   │                    │                    │
     │                   │ 13. Get email data │                    │
     │                   │<─────────────────────────────────────────│
     │                   │                    │                    │
     │ 14. Display emails │                    │                    │
     │<───────────────────                    │                    │
```

### Key OAuth Concepts

#### 1. **Client Credentials** (`credentials.json`)
```json
{
  "installed": {
    "client_id": "your-client-id.apps.googleusercontent.com",
    "client_secret": "your-client-secret",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["http://localhost:8767/"]
  }
}
```

- **Client ID**: Public identifier for your app
- **Client Secret**: Private key (keep this secret!)
- **Redirect URI**: Where Google sends the user after login

#### 2. **Scopes** (Permissions)
```python
scopes = [
    "https://www.googleapis.com/auth/gmail.readonly",  # Read emails
    "https://www.googleapis.com/auth/gmail.modify"     # Modify emails (delete, mark read)
]
```

#### 3. **Tokens**

- **Access Token**: Short-lived (1 hour), used for API calls
- **Refresh Token**: Long-lived, used to get new access tokens
- **Token Storage**: Saved in `token.json` after first login

---

## How Gmail Cleaner Uses OAuth

### Two Authentication Modes

#### Mode 1: Desktop App (Local Python)
- **When**: Running `uv run python main.py` locally
- **How**: Opens browser automatically, uses `localhost` redirect
- **Flow**: `InstalledAppFlow.run_local_server()`

#### Mode 2: Web Application (Docker/Remote)
- **When**: Running in Docker or on remote server
- **How**: Prints OAuth URL to logs, user copies and pastes
- **Flow**: Same OAuth flow, but manual browser opening

### The Authentication Process in Code

#### Step 1: Check for Existing Token
```python
# app/services/auth.py - get_gmail_service()

if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", scopes)
    if creds.valid:
        # Already authenticated! Use existing token
        return build("gmail", "v1", credentials=creds)
```

#### Step 2: Refresh Expired Token
```python
if creds.expired and creds.refresh_token:
    creds.refresh(Request())  # Get new access token
    # Save refreshed token
    with open("token.json", "w") as token:
        token.write(creds.to_json())
```

#### Step 3: Start OAuth Flow (If No Token)
```python
# Create OAuth flow from credentials.json
flow = InstalledAppFlow.from_client_secrets_file(
    "credentials.json",
    scopes
)

# Run local server to handle OAuth callback
new_creds = flow.run_local_server(
    port=8767,              # Port for OAuth callback
    bind_addr="0.0.0.0",    # Docker: 0.0.0.0, Local: localhost
    open_browser=True,      # Auto-open browser (local only)
    prompt="consent"        # Always show consent screen
)

# Save tokens
with open("token.json", "w") as token:
    token.write(new_creds.to_json())
```

### What Happens During OAuth?

1. **User clicks "Sign In"** → Frontend calls `/api/sign-in`
2. **Backend starts OAuth** → `get_gmail_service()` detects no token
3. **OAuth flow starts** → `flow.run_local_server()`:
   - Starts HTTP server on port 8767
   - Generates OAuth URL: `https://accounts.google.com/o/oauth2/auth?...`
   - Opens browser (or prints URL in Docker)
4. **User authorizes** → Google shows consent screen
5. **Google redirects** → `http://localhost:8767/?code=AUTHORIZATION_CODE`
6. **Server receives code** → Exchanges code for tokens
7. **Tokens saved** → Written to `token.json`
8. **Gmail API ready** → Can now make API calls

---

## Application Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Browser)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ auth.js  │  │scanner.js│  │delete.js │  │markread.js│   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │              │              │          │
│       └─────────────┴──────────────┴──────────────┘          │
│                          │                                    │
│                    HTTP/JSON API                               │
└──────────────────────────┼────────────────────────────────────┘
                           │
┌──────────────────────────┼────────────────────────────────────┐
│                    FastAPI Backend                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  actions.py  │  │  status.py   │  │   main.py    │      │
│  │  (POST)      │  │  (GET)       │  │  (Routes)     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                  │               │
│         └─────────────────┴──────────────────┘               │
│                          │                                    │
│  ┌───────────────────────┼───────────────────────┐            │
│  │              Services Layer                   │            │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐   │            │
│  │  │ auth.py  │  │ gmail/   │  │  state   │   │            │
│  │  │          │  │  scan.py  │  │          │   │            │
│  │  │          │  │ delete.py │  │          │   │            │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘   │            │
│  └───────┼─────────────┼──────────────┼────────┘            │
└──────────┼─────────────┼──────────────┼─────────────────────┘
           │             │              │
           │             │              │
    ┌──────┴─────┐  ┌─────┴──────┐  ┌───┴────┐
    │ OAuth 2.0 │  │ Gmail API  │  │ State  │
    │  Tokens   │  │  (REST)    │  │ (In-   │
    │           │  │            │  │ Memory)│
    └───────────┘  └────────────┘  └────────┘
```

### Component Breakdown

#### 1. **Frontend (Static Files)**
- **Location**: `static/js/`, `static/css/`, `templates/`
- **Technology**: Vanilla JavaScript, HTML, CSS
- **Purpose**: User interface, API calls, real-time updates

#### 2. **Backend API (FastAPI)**
- **Location**: `app/api/`, `app/main.py`
- **Endpoints**:
  - `POST /api/sign-in` - Start OAuth flow
  - `POST /api/scan` - Scan emails
  - `POST /api/delete-emails` - Delete emails
  - `GET /api/status` - Get operation status
  - `POST /api/mark-read` - Mark emails as read

#### 3. **Services Layer**
- **Location**: `app/services/`
- **auth.py**: OAuth authentication
- **gmail/**: Gmail API operations
  - `scan.py` - Find emails and unsubscribe links
  - `delete.py` - Delete emails
  - `mark_read.py` - Mark as read
  - `unsubscribe.py` - Unsubscribe from senders

#### 4. **State Management**
- **Location**: `app/core/state.py`
- **Purpose**: Track ongoing operations, scan results, user status
- **Storage**: In-memory (resets on restart)

---

## Gmail API Operations

### How Gmail API Works

Gmail API is a **REST API** that uses:
- **HTTP methods**: GET, POST, DELETE
- **Authentication**: OAuth 2.0 access tokens
- **Data format**: JSON

### Key Gmail API Endpoints Used

#### 1. **List Messages**
```python
# Get list of email IDs
service.users().messages().list(
    userId="me",
    maxResults=500,
    q="from:example@gmail.com"  # Gmail search query
).execute()
```

#### 2. **Get Message Details**
```python
# Get full email content
service.users().messages().get(
    userId="me",
    id="message_id",
    format="full"  # or "metadata", "minimal"
).execute()
```

#### 3. **Batch Requests** (Super Fast!)
```python
# Process 100 emails in one HTTP call
batch = service.new_batch_http_request()
for msg_id in message_ids:
    batch.add(
        service.users().messages().get(
            userId="me",
            id=msg_id,
            format="metadata"
        )
    )
batch.execute()  # One HTTP request for 100 emails!
```

#### 4. **Modify Messages**
```python
# Delete email (moves to trash)
service.users().messages().delete(
    userId="me",
    id="message_id"
).execute()

# Mark as read
service.users().messages().modify(
    userId="me",
    id="message_id",
    body={"removeLabelIds": ["UNREAD"]}
).execute()
```

### Example: Scanning Emails

```python
# 1. Get message IDs (fast - just IDs, not full emails)
result = service.users().messages().list(
    userId="me",
    maxResults=500,
    q="is:unread"  # Gmail search query
).execute()

message_ids = [m["id"] for m in result.get("messages", [])]

# 2. Get full email details in batches (100 at a time)
batch = service.new_batch_http_request()
for msg_id in message_ids[:100]:  # First 100
    batch.add(
        service.users().messages().get(
            userId="me",
            id=msg_id,
            format="full"
        )
    )

# 3. Process results
def process_message(request_id, response, exception):
    if exception:
        return

    # Extract unsubscribe link from headers
    headers = response.get("payload", {}).get("headers", [])
    for header in headers:
        if header["name"].lower() == "list-unsubscribe":
            unsubscribe_link = header["value"]
            # Save to results

batch.execute()  # One HTTP call processes 100 emails!
```

---

## Code Walkthrough

### 1. Starting the Application

**File**: `main.py`
```python
def main():
    # Check for credentials.json
    if not os.path.exists("credentials.json"):
        print("ERROR: credentials.json not found!")
        return

    # Start FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=8766)
```

**File**: `app/main.py`
```python
def create_app():
    app = FastAPI(title="Gmail Cleaner")

    # Mount static files (CSS, JS)
    app.mount("/static", StaticFiles(directory="static"))

    # Include API routers
    app.include_router(status_router)   # GET /api/status
    app.include_router(actions_router)   # POST /api/*

    # Serve HTML
    @app.get("/")
    async def root(request: Request):
        return templates.TemplateResponse("index.html", ...)

    return app
```

### 2. User Clicks "Sign In"

**Frontend** (`static/js/auth.js`):
```javascript
async function signIn() {
    const response = await fetch('/api/sign-in', {
        method: 'POST'
    });
    // Poll for auth status
    checkAuthStatus();
}
```

**Backend** (`app/api/actions.py`):
```python
@router.post("/sign-in")
async def api_sign_in(background_tasks: BackgroundTasks):
    # Start OAuth in background thread
    background_tasks.add_task(get_gmail_service)
    return {"status": "signing_in"}
```

**Service** (`app/services/auth.py`):
```python
def get_gmail_service():
    # Check for existing token
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", scopes)
        if creds.valid:
            return build("gmail", "v1", credentials=creds)

    # No token - start OAuth
    flow = InstalledAppFlow.from_client_secrets_file(
        "credentials.json", scopes
    )

    # This starts a local HTTP server on port 8767
    # and opens browser to Google login
    new_creds = flow.run_local_server(
        port=8767,
        open_browser=True
    )

    # Save tokens
    with open("token.json", "w") as token:
        token.write(new_creds.to_json())

    return build("gmail", "v1", credentials=new_creds)
```

### 3. Scanning Emails

**Frontend** (`static/js/scanner.js`):
```javascript
async function startScan(limit, filters) {
    await fetch('/api/scan', {
        method: 'POST',
        body: JSON.stringify({ limit, filters })
    });

    // Poll for results
    pollScanStatus();
}
```

**Backend** (`app/api/actions.py`):
```python
@router.post("/scan")
async def api_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    # Run scan in background (doesn't block API response)
    background_tasks.add_task(scan_emails, request.limit, filters)
    return {"status": "started"}
```

**Service** (`app/services/gmail/scan.py`):
```python
def scan_emails(limit=500, filters=None):
    # Get authenticated Gmail service
    service, error = get_gmail_service()

    # Build Gmail search query
    query = build_gmail_query(filters)  # e.g., "is:unread from:example@gmail.com"

    # Get message IDs (fast - just IDs)
    result = service.users().messages().list(
        userId="me",
        maxResults=limit,
        q=query
    ).execute()

    message_ids = [m["id"] for m in result.get("messages", [])]

    # Process in batches of 100
    batch = service.new_batch_http_request()
    for msg_id in message_ids:
        batch.add(
            service.users().messages().get(
                userId="me",
                id=msg_id,
                format="full"
            )
        )

    # Process results
    def process_message(request_id, response, exception):
        if exception:
            return

        # Extract unsubscribe link from email headers
        headers = response.get("payload", {}).get("headers", [])
        unsubscribe_link = get_unsubscribe_from_headers(headers)

        # Save to state
        state.scan_results[sender].append({
            "link": unsubscribe_link,
            "count": 1
        })

    batch.execute()  # One HTTP call for 100 emails!

    # Update status
    state.scan_status["done"] = True
```

### 4. Deleting Emails

**Service** (`app/services/gmail/delete.py`):
```python
def delete_emails_by_sender(sender):
    service, error = get_gmail_service()

    # Find all emails from sender
    result = service.users().messages().list(
        userId="me",
        q=f"from:{sender}"
    ).execute()

    message_ids = [m["id"] for m in result.get("messages", [])]

    # Delete in batches
    batch = service.new_batch_http_request()
    for msg_id in message_ids:
        batch.add(
            service.users().messages().delete(
                userId="me",
                id=msg_id
            )
        )

    batch.execute()  # Delete 100 emails in one HTTP call!
```

---

## Key Design Decisions

### 1. **Why Background Tasks?**
- Long-running operations (scanning 1000s of emails) would timeout HTTP requests
- Background tasks let API return immediately: `{"status": "started"}`
- Frontend polls `/api/status` for progress

### 2. **Why Batch Requests?**
- Gmail API allows 100 requests in one HTTP call
- **10x faster** than individual requests
- Reduces API quota usage

### 3. **Why State Management?**
- Operations run in background threads
- State (`app/core/state.py`) tracks:
  - Current operation status
  - Scan results
  - Progress counters
- Frontend polls state via `/api/status`

### 4. **Why Two Auth Modes?**
- **Desktop**: Auto-opens browser (better UX)
- **Docker/Remote**: Can't auto-open browser, prints URL instead

---

## Security Considerations

### 1. **Credentials Storage**
- `credentials.json` - Contains client secret (gitignored)
- `token.json` - Contains refresh token (gitignored)
- Never commit these files!

### 2. **Token Refresh**
- Access tokens expire after 1 hour
- Refresh token automatically gets new access token
- No user interaction needed after first login

### 3. **Scopes (Minimal Permissions)**
- Only requests `gmail.readonly` and `gmail.modify`
- No access to other Google services
- User can revoke access anytime in Google Account settings

---

## Summary

1. **OAuth Flow**: User grants permission → Google gives tokens → App uses tokens for API calls
2. **Architecture**: Frontend (JS) → FastAPI Backend → Gmail API
3. **Performance**: Batch requests (100 emails per HTTP call)
4. **State**: In-memory state tracked via background tasks
5. **Security**: Tokens stored locally, never committed to git

The app is **privacy-focused** because:
- Each user creates their own OAuth app
- All processing happens locally
- No data sent to external servers
- Open source - you can inspect everything!
