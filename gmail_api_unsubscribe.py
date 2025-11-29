#!/usr/bin/env python3
"""
Gmail Bulk Unsubscribe Tool - Gmail API Version (FAST!)
--------------------------------------------------------
Uses Gmail API for batch requests - nearly instant results like paid services!

SETUP (one-time, ~5 minutes):
1. Go to https://console.cloud.google.com/
2. Create a new project (or select existing)
3. Enable Gmail API: APIs & Services > Enable APIs > Search "Gmail API" > Enable
4. Create OAuth credentials:
   - APIs & Services > Credentials > Create Credentials > OAuth client ID
   - Configure consent screen first (External, just your email for testing)
   - Application type: Desktop app
   - Download the JSON file
5. Rename downloaded file to "credentials.json" and put it in this folder
6. Run this script!
"""

import os
import json
import base64
import re
import html
from collections import defaultdict
from datetime import datetime
import http.server
import socketserver
import threading
import webbrowser
import urllib.request
import ssl

# Gmail API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Gmail API scope - read-only access to emails
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

PORT = 8766
scan_results = []
scan_status = {"progress": 0, "message": "Ready", "done": False, "error": None}
current_user = {"email": None, "logged_in": False}

# ============== Gmail API Functions ==============

def get_gmail_service():
    """Get authenticated Gmail API service."""
    global current_user
    creds = None
    
    # Token file stores user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If no valid credentials, let user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                return None, "credentials.json not found! Please follow setup instructions."
            
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    service = build('gmail', 'v1', credentials=creds)
    
    # Get user's email address
    try:
        profile = service.users().getProfile(userId='me').execute()
        current_user['email'] = profile.get('emailAddress', 'Unknown')
        current_user['logged_in'] = True
    except:
        current_user['email'] = 'Unknown'
        current_user['logged_in'] = True
    
    return service, None


def sign_out():
    """Sign out by removing the token file."""
    global current_user, scan_results, scan_status
    
    if os.path.exists('token.json'):
        os.remove('token.json')
    
    current_user = {"email": None, "logged_in": False}
    scan_results = []
    scan_status = {"progress": 0, "message": "Ready", "done": False, "error": None}
    
    return {"success": True, "message": "Signed out successfully"}


def check_login_status():
    """Check if user is logged in and get their email."""
    global current_user
    
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            if creds and creds.valid:
                service = build('gmail', 'v1', credentials=creds)
                profile = service.users().getProfile(userId='me').execute()
                current_user['email'] = profile.get('emailAddress', 'Unknown')
                current_user['logged_in'] = True
                return current_user
            elif creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
                service = build('gmail', 'v1', credentials=creds)
                profile = service.users().getProfile(userId='me').execute()
                current_user['email'] = profile.get('emailAddress', 'Unknown')
                current_user['logged_in'] = True
                return current_user
        except:
            pass
    
    current_user = {"email": None, "logged_in": False}
    return current_user


def get_unsubscribe_from_headers(headers):
    """Extract unsubscribe link from email headers."""
    for header in headers:
        if header['name'].lower() == 'list-unsubscribe':
            value = header['value']
            # Extract HTTP URL
            urls = re.findall(r'<(https?://[^>]+)>', value)
            if urls:
                return urls[0]
            # Check for mailto as fallback
            mailto = re.findall(r'<(mailto:[^>]+)>', value)
            if mailto:
                return mailto[0]
    return None


def get_sender_info(headers):
    """Extract sender email and domain from headers."""
    for header in headers:
        if header['name'].lower() == 'from':
            from_value = header['value']
            # Extract email
            email_match = re.search(r'[\w.-]+@[\w.-]+', from_value)
            if email_match:
                email = email_match.group()
                domain = email.split('@')[1].lower()
                return from_value, domain
    return "", "unknown"


def get_subject(headers):
    """Extract subject from headers."""
    for header in headers:
        if header['name'].lower() == 'subject':
            return header['value'][:60]
    return ""


def scan_emails_api(limit=500):
    """Scan emails using Gmail API - FAST batch requests!"""
    global scan_results, scan_status
    
    scan_results = []
    scan_status = {"progress": 5, "message": "Connecting to Gmail API...", "done": False, "error": None}
    
    try:
        service, error = get_gmail_service()
        if error:
            scan_status = {"progress": 0, "message": error, "done": True, "error": error}
            return
        
        scan_status = {"progress": 10, "message": "Fetching email list...", "done": False, "error": None}
        
        # Get list of message IDs (very fast - just IDs)
        results = service.users().messages().list(
            userId='me',
            maxResults=limit,
            q='category:promotions OR category:updates OR unsubscribe'  # Focus on likely newsletters
        ).execute()
        
        messages = results.get('messages', [])
        
        if not messages:
            scan_status = {"progress": 100, "message": "No emails found", "done": True, "error": None}
            return
        
        scan_status = {"progress": 15, "message": f"Found {len(messages)} emails, batch fetching...", "done": False, "error": None}
        
        # Use TRUE batch requests - much faster!
        senders_data = defaultdict(lambda: {
            'count': 0,
            'links': set(),
            'subjects': [],
            'from': ''
        })
        
        from googleapiclient.http import BatchHttpRequest
        
        total = len(messages)
        processed = [0]  # Use list to allow modification in nested function
        
        def process_message(request_id, response, exception):
            """Callback for batch request"""
            processed[0] += 1
            
            if exception is not None:
                return
            
            headers = response.get('payload', {}).get('headers', [])
            
            unsub_link = get_unsubscribe_from_headers(headers)
            
            if unsub_link and unsub_link.startswith('http'):
                from_value, domain = get_sender_info(headers)
                subject = get_subject(headers)
                
                senders_data[domain]['count'] += 1
                senders_data[domain]['links'].add(unsub_link)
                senders_data[domain]['from'] = from_value
                if len(senders_data[domain]['subjects']) < 3:
                    senders_data[domain]['subjects'].append(subject)
        
        # Process in batches of 100 (Gmail API limit)
        batch_size = 100
        
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            
            # Create batch request
            batch = service.new_batch_http_request(callback=process_message)
            
            for msg in messages[batch_start:batch_end]:
                batch.add(
                    service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='metadata',
                        metadataHeaders=['From', 'Subject', 'List-Unsubscribe']
                    )
                )
            
            # Execute batch (single HTTP call for up to 100 emails!)
            batch.execute()
            
            progress = 15 + int((batch_end / total) * 80)
            scan_status = {"progress": progress, "message": f"Batch fetched {batch_end}/{total} emails", "done": False, "error": None}
        
        # Sort by count and prepare results
        sorted_senders = sorted(senders_data.items(), key=lambda x: x[1]['count'], reverse=True)
        
        for domain, data in sorted_senders:
            http_links = [l for l in data['links'] if l.startswith('http')]
            if http_links:
                scan_results.append({
                    'domain': domain,
                    'count': data['count'],
                    'from': data['from'],
                    'link': http_links[0],
                    'subjects': data['subjects']
                })
        
        scan_status = {"progress": 100, "message": f"Done! Found {len(scan_results)} senders", "done": True, "error": None}
        
    except HttpError as e:
        scan_status = {"progress": 0, "message": f"Gmail API error: {e}", "done": True, "error": str(e)}
    except Exception as e:
        scan_status = {"progress": 0, "message": f"Error: {e}", "done": True, "error": str(e)}


def unsubscribe_single(domain, link):
    """Unsubscribe from a single sender."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        req = urllib.request.Request(link, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        
        response = urllib.request.urlopen(req, timeout=10, context=ctx)
        content = response.read().decode('utf-8', errors='ignore').lower()
        
        success_words = ['unsubscribed', 'removed', 'success', 'confirmed', 'you have been', 'opt out']
        if any(word in content for word in success_words):
            return {"success": True, "status": "Unsubscribed!"}
        return {"success": True, "status": "Link visited"}
        
    except urllib.error.HTTPError as e:
        if e.code in [301, 302, 303, 307, 308]:
            return {"success": True, "status": "Redirected"}
        return {"success": False, "status": f"HTTP {e.code}"}
    except Exception as e:
        return {"success": False, "status": str(e)[:30]}


# ============== Web Server ==============

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ Gmail Unsubscribe - API Version</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1000px; margin: 0 auto; }
        
        h1 { text-align: center; font-size: 2.5em; margin-bottom: 10px; }
        .subtitle { text-align: center; color: #a0a0a0; margin-bottom: 30px; }
        .fast-badge { 
            background: linear-gradient(135deg, #00d26a, #00b359); 
            padding: 3px 12px; 
            border-radius: 20px; 
            font-size: 0.5em;
            vertical-align: middle;
        }
        
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h2 { margin-bottom: 15px; font-size: 1.3em; color: #00d26a; }
        
        .user-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(0,210,106,0.15);
            border: 1px solid #00d26a;
            border-radius: 10px;
            padding: 15px 20px;
            margin-bottom: 20px;
        }
        .user-info { display: flex; align-items: center; gap: 10px; }
        .user-avatar { 
            width: 40px; height: 40px; 
            background: linear-gradient(135deg, #00d26a, #00b359);
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.2em;
        }
        .user-email { font-weight: bold; }
        .user-label { color: #888; font-size: 0.85em; }
        
        .login-box {
            text-align: center;
            padding: 40px;
        }
        .login-box p { color: #888; margin-bottom: 20px; }
        
        .setup-steps { background: rgba(0,210,106,0.1); border-left: 4px solid #00d26a; padding: 15px; border-radius: 0 8px 8px 0; margin-bottom: 20px; }
        .setup-steps h3 { color: #00d26a; margin-bottom: 10px; }
        .setup-steps ol { margin-left: 20px; color: #ccc; }
        .setup-steps li { margin-bottom: 8px; }
        .setup-steps a { color: #00d26a; }
        .setup-steps code { background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; }
        
        .status-box { padding: 15px; border-radius: 8px; margin-bottom: 15px; }
        .status-ready { background: rgba(0,210,106,0.2); border: 1px solid #00d26a; }
        .status-error { background: rgba(233,69,96,0.2); border: 1px solid #e94560; }
        
        .form-row { display: flex; gap: 15px; align-items: flex-end; flex-wrap: wrap; }
        .form-group { flex: 1; min-width: 150px; }
        .form-group label { display: block; margin-bottom: 8px; color: #ccc; }
        select { width: 100%; padding: 12px; border: none; border-radius: 8px; background: rgba(255,255,255,0.1); color: #fff; font-size: 1em; }
        
        .btn {
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary { background: linear-gradient(135deg, #00d26a, #00b359); color: #fff; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(0,210,106,0.4); }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-danger { background: linear-gradient(135deg, #e94560, #c23a51); color: #fff; }
        .btn-danger:hover { transform: translateY(-2px); }
        .btn-secondary { background: rgba(255,255,255,0.1); color: #fff; }
        .btn-sm { padding: 8px 16px; font-size: 0.9em; }
        
        .progress-container { background: rgba(0,0,0,0.3); border-radius: 10px; height: 25px; overflow: hidden; margin: 15px 0; }
        .progress-bar { height: 100%; background: linear-gradient(90deg, #00d26a, #00ff88); border-radius: 10px; transition: width 0.3s; display: flex; align-items: center; justify-content: center; font-weight: bold; }
        
        .results-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; flex-wrap: wrap; gap: 10px; }
        .results-actions { display: flex; gap: 10px; }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 15px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { background: rgba(0,0,0,0.2); color: #00d26a; }
        tr:hover { background: rgba(255,255,255,0.05); }
        
        .badge { background: #00d26a; color: #000; padding: 3px 10px; border-radius: 20px; font-size: 0.85em; font-weight: bold; }
        
        .unsub-btn { background: linear-gradient(135deg, #e94560, #c23a51); color: #fff; padding: 6px 14px; border-radius: 5px; border: none; cursor: pointer; font-size: 0.85em; }
        .unsub-btn:hover { transform: scale(1.05); }
        .unsub-btn:disabled { opacity: 0.5; }
        .unsub-btn.success { background: #00d26a; }
        .unsub-btn.failed { background: #666; }
        
        .link-btn { background: #1a1a3e; color: #fff; padding: 6px 10px; border-radius: 5px; text-decoration: none; font-size: 0.85em; margin-left: 5px; }
        
        .empty-state { text-align: center; padding: 50px; color: #666; }
        .empty-state span { font-size: 4em; display: block; margin-bottom: 20px; }
        
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ Gmail Bulk Unsubscribe <span class="fast-badge">API - FAST!</span></h1>
        <p class="subtitle">10x faster than IMAP - uses Gmail API batch requests</p>
        
        <!-- User Bar (shown when logged in) -->
        <div class="user-bar hidden" id="userBar">
            <div class="user-info">
                <div class="user-avatar">👤</div>
                <div>
                    <div class="user-label">Signed in as</div>
                    <div class="user-email" id="userEmail">loading...</div>
                </div>
            </div>
            <button class="btn btn-danger btn-sm" onclick="signOut()">🚪 Sign Out</button>
        </div>
        
        <!-- Login Box (shown when not logged in) -->
        <div class="card hidden" id="loginBox">
            <div class="login-box">
                <h2>🔐 Sign In to Gmail</h2>
                <p>Click below to sign in with your Google account</p>
                <button class="btn btn-primary" onclick="signIn()">🚀 Sign In with Google</button>
            </div>
        </div>
        
        <div class="setup-steps" id="setupBox">
            <h3>📋 One-Time Setup (if not done yet)</h3>
            <ol>
                <li>Go to <a href="https://console.cloud.google.com/" target="_blank">console.cloud.google.com</a></li>
                <li>Create new project → Name it "Gmail Unsubscribe"</li>
                <li>Go to <strong>APIs & Services</strong> → <strong>Enable APIs</strong> → Search "Gmail API" → <strong>Enable</strong></li>
                <li>Go to <strong>APIs & Services</strong> → <strong>OAuth consent screen</strong> → External → Add your email as test user</li>
                <li>Go to <strong>Credentials</strong> → <strong>Create Credentials</strong> → <strong>OAuth client ID</strong> → Desktop app</li>
                <li>Download JSON → Rename to <code>credentials.json</code> → Put in this folder</li>
            </ol>
        </div>
        
        <div class="card hidden" id="scanCard">
            <h2>🔍 Scan Emails</h2>
            <div id="statusBox" class="status-box status-ready">
                <span id="statusText">Ready to scan. Click the button to start!</span>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Number of emails to scan</label>
                    <select id="limit">
                        <option value="100">100 (fastest)</option>
                        <option value="250">250</option>
                        <option value="500" selected>500 (recommended)</option>
                        <option value="1000">1000</option>
                        <option value="2000">2000</option>
                    </select>
                </div>
                <div class="form-group" style="flex: 0;">
                    <label>&nbsp;</label>
                    <button class="btn btn-primary" id="scanBtn" onclick="startScan()">⚡ Scan Emails</button>
                </div>
            </div>
        </div>
        
        <div class="card hidden" id="progressCard">
            <h2>📊 Progress</h2>
            <div class="progress-container">
                <div class="progress-bar" id="progressBar" style="width: 0%;">0%</div>
            </div>
            <p id="progressText" style="color: #aaa; margin-top: 10px;">Starting...</p>
        </div>
        
        <div class="card hidden" id="resultsCard">
            <div class="results-header">
                <h2>📬 Unsubscribe Opportunities <span class="badge" id="resultCount">0</span></h2>
                <div class="results-actions">
                    <button class="btn btn-secondary" onclick="selectAll()">Select All</button>
                    <button class="btn btn-danger" onclick="autoUnsubscribe()">⚡ Unsubscribe All Selected</button>
                    <button class="btn btn-secondary" onclick="exportLinks()">💾 Export</button>
                </div>
            </div>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 50px;"><input type="checkbox" id="selectAllCheckbox" onchange="toggleAll()"></th>
                            <th>Sender</th>
                            <th style="width: 80px;"># Emails</th>
                            <th>Sample Subject</th>
                            <th style="width: 180px;">Action</th>
                        </tr>
                    </thead>
                    <tbody id="resultsBody"></tbody>
                </table>
            </div>
            <div class="empty-state hidden" id="emptyState">
                <span>📭</span>
                <p>No unsubscribe links found.</p>
            </div>
        </div>
    </div>
    
    <script>
        let results = [];
        let scanning = false;
        
        // Check login status on page load
        window.onload = checkLoginStatus;
        
        async function checkLoginStatus() {
            try {
                const response = await fetch('/auth-status');
                const status = await response.json();
                updateUI(status);
            } catch (error) {
                console.error('Error checking login status:', error);
            }
        }
        
        function updateUI(authStatus) {
            const userBar = document.getElementById('userBar');
            const loginBox = document.getElementById('loginBox');
            const scanCard = document.getElementById('scanCard');
            const setupBox = document.getElementById('setupBox');
            
            if (authStatus.logged_in) {
                userBar.classList.remove('hidden');
                loginBox.classList.add('hidden');
                scanCard.classList.remove('hidden');
                setupBox.classList.add('hidden');
                document.getElementById('userEmail').textContent = authStatus.email;
            } else {
                userBar.classList.add('hidden');
                loginBox.classList.remove('hidden');
                scanCard.classList.add('hidden');
                document.getElementById('resultsCard').classList.add('hidden');
                document.getElementById('progressCard').classList.add('hidden');
            }
        }
        
        async function signIn() {
            // Trigger sign in by starting a scan (which will prompt for auth)
            document.getElementById('loginBox').innerHTML = '<div class="login-box"><p>🔄 Opening Google Sign In...</p></div>';
            
            try {
                await fetch('/sign-in', { method: 'POST' });
                // Poll for login completion
                pollLoginStatus();
            } catch (error) {
                alert('Error signing in: ' + error.message);
            }
        }
        
        async function pollLoginStatus() {
            const response = await fetch('/auth-status');
            const status = await response.json();
            
            if (status.logged_in) {
                updateUI(status);
            } else {
                setTimeout(pollLoginStatus, 1000);
            }
        }
        
        async function signOut() {
            if (!confirm('Sign out from ' + document.getElementById('userEmail').textContent + '?')) return;
            
            try {
                await fetch('/sign-out', { method: 'POST' });
                document.getElementById('resultsCard').classList.add('hidden');
                document.getElementById('progressCard').classList.add('hidden');
                results = [];
                checkLoginStatus();
            } catch (error) {
                alert('Error signing out: ' + error.message);
            }
        }
        
        async function startScan() {
            if (scanning) return;
            
            scanning = true;
            document.getElementById('scanBtn').disabled = true;
            document.getElementById('scanBtn').textContent = '⏳ Scanning...';
            document.getElementById('progressCard').classList.remove('hidden');
            document.getElementById('resultsCard').classList.add('hidden');
            
            const limit = document.getElementById('limit').value;
            
            try {
                await fetch('/scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ limit: parseInt(limit) })
                });
                pollProgress();
            } catch (error) {
                alert('Error: ' + error.message);
                resetScan();
            }
        }
        
        async function pollProgress() {
            try {
                const response = await fetch('/status');
                const status = await response.json();
                
                document.getElementById('progressBar').style.width = status.progress + '%';
                document.getElementById('progressBar').textContent = status.progress + '%';
                document.getElementById('progressText').textContent = status.message;
                
                if (status.error) {
                    document.getElementById('statusBox').className = 'status-box status-error';
                    document.getElementById('statusText').textContent = status.error;
                }
                
                if (status.done) {
                    if (!status.error) {
                        const resultsResponse = await fetch('/results');
                        results = await resultsResponse.json();
                        displayResults();
                        document.getElementById('statusBox').className = 'status-box status-ready';
                        document.getElementById('statusText').textContent = 'Scan complete! Found ' + results.length + ' senders.';
                    }
                    resetScan();
                } else {
                    setTimeout(pollProgress, 300);
                }
            } catch (error) {
                setTimeout(pollProgress, 500);
            }
        }
        
        function resetScan() {
            scanning = false;
            document.getElementById('scanBtn').disabled = false;
            document.getElementById('scanBtn').textContent = '⚡ Scan Emails';
        }
        
        function displayResults() {
            document.getElementById('resultsCard').classList.remove('hidden');
            document.getElementById('resultCount').textContent = results.length;
            
            const tbody = document.getElementById('resultsBody');
            tbody.innerHTML = '';
            
            if (results.length === 0) {
                document.getElementById('emptyState').classList.remove('hidden');
                return;
            }
            document.getElementById('emptyState').classList.add('hidden');
            
            results.forEach((r, i) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="checkbox" class="result-checkbox" data-index="${i}"></td>
                    <td><strong>${escapeHtml(r.domain)}</strong></td>
                    <td><span class="badge">${r.count}</span></td>
                    <td>${escapeHtml(r.subjects[0] || '')}</td>
                    <td>
                        <button class="unsub-btn" id="unsub-btn-${i}" onclick="unsubscribeSingle(${i})">🚫 Unsubscribe</button>
                        <a href="${escapeHtml(r.link)}" target="_blank" class="link-btn">↗</a>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text || '';
            return div.innerHTML;
        }
        
        function selectAll() {
            const checkboxes = document.querySelectorAll('.result-checkbox');
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            checkboxes.forEach(cb => cb.checked = !allChecked);
            document.getElementById('selectAllCheckbox').checked = !allChecked;
        }
        
        function toggleAll() {
            const checked = document.getElementById('selectAllCheckbox').checked;
            document.querySelectorAll('.result-checkbox').forEach(cb => cb.checked = checked);
        }
        
        async function unsubscribeSingle(index) {
            const r = results[index];
            const btn = document.getElementById('unsub-btn-' + index);
            
            btn.disabled = true;
            btn.textContent = '⏳...';
            
            try {
                const response = await fetch('/unsubscribe-one', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ domain: r.domain, link: r.link })
                });
                const result = await response.json();
                
                if (result.success) {
                    btn.textContent = '✓ Done';
                    btn.classList.add('success');
                } else {
                    btn.textContent = '↗ Open';
                    btn.classList.add('failed');
                    btn.onclick = () => window.open(r.link, '_blank');
                    btn.disabled = false;
                }
            } catch (error) {
                btn.textContent = '↗ Open';
                btn.disabled = false;
            }
        }
        
        async function autoUnsubscribe() {
            const indices = [];
            document.querySelectorAll('.result-checkbox:checked').forEach(cb => {
                const index = parseInt(cb.dataset.index);
                const btn = document.getElementById('unsub-btn-' + index);
                if (!btn.classList.contains('success')) indices.push(index);
            });
            
            if (indices.length === 0) {
                alert('No items selected!');
                return;
            }
            
            if (!confirm('Unsubscribe from ' + indices.length + ' senders?')) return;
            
            for (const idx of indices) {
                await unsubscribeSingle(idx);
                await new Promise(r => setTimeout(r, 200));
            }
        }
        
        function exportLinks() {
            if (!results.length) return alert('No results to export');
            
            let text = 'Gmail Unsubscribe Links\\n' + '='.repeat(50) + '\\n\\n';
            results.forEach((r, i) => {
                text += (i+1) + '. ' + r.domain + '\\n   Emails: ' + r.count + '\\n   Link: ' + r.link + '\\n\\n';
            });
            
            const blob = new Blob([text], { type: 'text/plain' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'unsubscribe_links.txt';
            a.click();
        }
    </script>
</body>
</html>
"""


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(scan_status).encode())
        elif self.path == '/results':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(scan_results).encode())
        else:
            self.send_error(404)
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode())
        
        if self.path == '/scan':
            thread = threading.Thread(target=scan_emails_api, args=(data.get('limit', 500),))
            thread.daemon = True
            thread.start()
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started"}).encode())
            
        elif self.path == '/unsubscribe-one':
            result = unsubscribe_single(data['domain'], data['link'])
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        pass


def main():
    print("=" * 60)
    print("⚡ Gmail Bulk Unsubscribe - API Version (FAST!)")
    print("=" * 60)
    
    # Check for credentials
    if not os.path.exists('credentials.json'):
        print("\n⚠️  credentials.json not found!")
        print("\nSetup instructions:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create project → Enable Gmail API")
        print("3. Create OAuth credentials (Desktop app)")
        print("4. Download JSON → rename to credentials.json")
        print("5. Put credentials.json in:", os.getcwd())
        print("\nOpening browser with instructions...")
    else:
        print("\n✅ credentials.json found!")
    
    print(f"\n🌐 Opening browser at: http://localhost:{PORT}")
    print("   (Keep this terminal open)")
    print("\n   Press Ctrl+C to stop\n")
    
    threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{PORT}')).start()
    
    # Allow port reuse to avoid "Address already in use" error
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Stopped!")


if __name__ == "__main__":
    main()
