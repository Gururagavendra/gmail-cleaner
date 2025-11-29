"""
Gmail API Module
----------------
Handles all Gmail API interactions: authentication, email scanning, unsubscribe.
"""

import os
import re
import base64
import json
import time
import urllib.request
import ssl
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from googleapiclient.discovery import build

# Gmail API scopes - read and modify for marking as read
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.modify']

# Global state
current_user = {"email": None, "logged_in": False}
scan_results = []
scan_status = {"progress": 0, "message": "Ready", "done": False, "error": None}
pending_auth_url = {"url": None}  # Store pending OAuth URL for web UI
auth_in_progress = {"active": False}  # Prevent multiple OAuth attempts

def is_web_auth_mode():
    """Check if we should use web-based auth (for Docker/headless)."""
    return os.environ.get('WEB_AUTH', '').lower() == 'true'

def needs_auth_setup():
    """Check if authentication is needed."""
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            if creds and (creds.valid or creds.refresh_token):
                return False
        except:
            pass
    return True

def get_web_auth_status():
    """Get current web auth status."""
    return {
        "needs_setup": needs_auth_setup(),
        "web_auth_mode": is_web_auth_mode(),
        "has_credentials": os.path.exists('credentials.json'),
        "pending_auth_url": pending_auth_url["url"]
    }


# OAuth callback port - fixed for Docker compatibility
OAUTH_PORT = 8767


import json

def get_credentials_path():
    """Get credentials - from file or create from env var."""
    if os.path.exists('credentials.json'):
        return 'credentials.json'
    
    # Check for env var (for cloud deployment)
    env_creds = os.environ.get('GOOGLE_CREDENTIALS')
    if env_creds:
        # Write env var to temp file
        with open('credentials.json', 'w') as f:
            f.write(env_creds)
        return 'credentials.json'
    
    return None


def get_gmail_service():
    """Get authenticated Gmail API service."""
    global current_user
    creds = None
    
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        else:
            # Prevent multiple OAuth attempts
            if auth_in_progress["active"]:
                return None, "Sign-in already in progress. Please complete the authorization in your browser."
            
            creds_path = get_credentials_path()
            if not creds_path:
                return None, "credentials.json not found! Please follow setup instructions."
            
            # Start OAuth in background thread so Flask stays responsive
            auth_in_progress["active"] = True
            
            def run_oauth():
                try:
                    # Use fixed port 8767 for OAuth callback (works with Docker port mapping)
                    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                    
                    # Check if we're in Docker (no display) or local
                    import shutil
                    has_browser = shutil.which('xdg-open') or shutil.which('open') or os.environ.get('DISPLAY')
                    
                    # For Docker: bind to 0.0.0.0 so callback can reach container
                    # For local: bind to localhost for security
                    bind_address = "0.0.0.0" if is_web_auth_mode() else "localhost"
                    
                    # run_local_server handles everything - generates URL, starts callback server
                    creds = flow.run_local_server(
                        port=OAUTH_PORT, 
                        bind_addr=bind_address,
                        open_browser=has_browser
                    )
                    
                    with open('token.json', 'w') as token:
                        token.write(creds.to_json())
                    print("✅ OAuth complete! Token saved.")
                except Exception as e:
                    print(f"❌ OAuth error: {e}")
                finally:
                    auth_in_progress["active"] = False
                    pending_auth_url["url"] = None
            
            oauth_thread = threading.Thread(target=run_oauth, daemon=True)
            oauth_thread.start()
            
            return None, "Sign-in started. Please complete authorization in your browser (check logs for URL)."
    
    service = build('gmail', 'v1', credentials=creds)
    
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
    scan_results = []  # Clear results
    scan_status = {"progress": 0, "message": "Ready", "done": False, "error": None}
    
    print("🚪 Signed out - results cleared")
    return {"success": True, "message": "Signed out successfully", "results_cleared": True}


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
            urls = re.findall(r'<(https?://[^>]+)>', value)
            if urls:
                return urls[0]
            mailto = re.findall(r'<(mailto:[^>]+)>', value)
            if mailto:
                return mailto[0]
    return None


def get_sender_info(headers):
    """Extract sender email and domain from headers."""
    for header in headers:
        if header['name'].lower() == 'from':
            value = header['value']
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', value)
            if email_match:
                email = email_match.group().lower()
                domain = email.split('@')[1] if '@' in email else email
                return email, domain
    return None, None


def get_subject(headers):
    """Extract subject from headers."""
    for header in headers:
        if header['name'].lower() == 'subject':
            return header['value']
    return "(No Subject)"


def scan_emails(limit=500):
    """Scan emails for unsubscribe links using batch requests."""
    global scan_results, scan_status
    
    scan_status = {"progress": 0, "message": "Connecting to Gmail...", "done": False, "error": None}
    scan_results = []
    
    service, error = get_gmail_service()
    if error:
        scan_status = {"progress": 0, "message": "", "done": True, "error": error}
        return
    
    try:
        scan_status["message"] = "Fetching email list..."
        
        # Get message IDs
        message_ids = []
        page_token = None
        
        while len(message_ids) < limit:
            result = service.users().messages().list(
                userId='me',
                maxResults=min(500, limit - len(message_ids)),
                pageToken=page_token
            ).execute()
            
            messages = result.get('messages', [])
            message_ids.extend([m['id'] for m in messages])
            
            page_token = result.get('nextPageToken')
            if not page_token:
                break
        
        if not message_ids:
            scan_status = {"progress": 100, "message": "No emails found", "done": True, "error": None}
            return
        
        total = len(message_ids)
        scan_status["message"] = f"Found {total} emails. Scanning with batch requests..."
        
        # Process in batches
        unsubscribe_data = defaultdict(lambda: {"link": None, "count": 0, "subjects": []})
        processed = 0
        batch_size = 100
        
        def process_message(request_id, response, exception):
            nonlocal processed
            processed += 1
            
            if exception:
                return
            
            headers = response.get('payload', {}).get('headers', [])
            unsub_link = get_unsubscribe_from_headers(headers)
            
            if unsub_link and not unsub_link.startswith('mailto:'):
                _, domain = get_sender_info(headers)
                if domain:
                    subject = get_subject(headers)
                    unsubscribe_data[domain]["link"] = unsub_link
                    unsubscribe_data[domain]["count"] += 1
                    if len(unsubscribe_data[domain]["subjects"]) < 3:
                        unsubscribe_data[domain]["subjects"].append(subject)
        
        for i in range(0, len(message_ids), batch_size):
            batch_ids = message_ids[i:i + batch_size]
            batch = service.new_batch_http_request(callback=process_message)
            
            for msg_id in batch_ids:
                batch.add(
                    service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='metadata',
                        metadataHeaders=['From', 'Subject', 'List-Unsubscribe']
                    )
                )
            
            batch.execute()
            
            progress = int((i + len(batch_ids)) / total * 100)
            scan_status["progress"] = progress
            scan_status["message"] = f"Scanned {processed}/{total} emails ({len(unsubscribe_data)} senders found)"
            
            # Rate limiting - small delay every 5 batches (500 emails)
            if (i // batch_size + 1) % 5 == 0:
                time.sleep(0.5)
        
        # Sort by count
        sorted_results = sorted(
            [{"domain": k, "link": v["link"], "count": v["count"], "subjects": v["subjects"]} 
             for k, v in unsubscribe_data.items()],
            key=lambda x: x["count"],
            reverse=True
        )
        
        # Test links in PARALLEL for speed (10 at a time)
        scan_status["message"] = f"Testing {len(sorted_results)} links in parallel..."
        
        def test_link_wrapper(item):
            item["type"] = test_unsubscribe_link(item["link"])
            return item
        
        tested_count = 0
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(test_link_wrapper, item): item for item in sorted_results}
            
            for future in as_completed(futures):
                tested_count += 1
                scan_status["progress"] = int(tested_count / len(sorted_results) * 100)
                scan_status["message"] = f"Testing links... {tested_count}/{len(sorted_results)}"
        
        scan_results = sorted_results
        
        # Count types
        one_click = sum(1 for r in scan_results if r.get("type") == "one-click")
        manual = len(scan_results) - one_click
        
        scan_status = {
            "progress": 100,
            "message": f"Done! {one_click} auto-unsubscribe, {manual} need manual action",
            "done": True,
            "error": None
        }
        
    except Exception as e:
        scan_status = {"progress": 0, "message": "", "done": True, "error": str(e)}


def test_unsubscribe_link(link):
    """
    Test if an unsubscribe link is one-click or needs manual action.
    Returns: 'one-click' only if SURE it worked, otherwise 'manual'
    """
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(link, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        response = urllib.request.urlopen(req, timeout=5, context=ctx)
        html = response.read().decode('utf-8', errors='ignore').lower()
        
        # Success indicators - one-click worked! (be strict)
        success_phrases = [
            'successfully unsubscribed', 'you have been unsubscribed', 
            'unsubscribe successful', 'you are now unsubscribed',
            'you have been removed', 'subscription cancelled',
            'you will no longer receive', 'email address has been removed',
            'opt-out successful', "you've been unsubscribed",
            'you have unsubscribed', 'unsubscription confirmed'
        ]
        
        for phrase in success_phrases:
            if phrase in html:
                return 'one-click'
        
        # Everything else needs manual action
        return 'manual'
        
    except Exception as e:
        return 'manual'


def unsubscribe_single(domain, link):
    """Attempt to unsubscribe by visiting the link."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(link, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        response = urllib.request.urlopen(req, timeout=10, context=ctx)
        html = response.read().decode('utf-8', errors='ignore').lower()
        
        # Check if unsubscribe was successful
        success_words = [
            'successfully unsubscribed', 'you have been unsubscribed', 
            'unsubscribe successful', 'you are now unsubscribed',
            'removed from', 'you have been removed', 'subscription cancelled',
            'you will no longer receive', 'email address has been removed'
        ]
        
        for word in success_words:
            if word in html:
                return {"success": True, "domain": domain, "status": "unsubscribed", "message": "Successfully unsubscribed!"}
        
        return {"success": False, "domain": domain, "status": "manual_needed", "message": "Page loaded but needs manual confirmation"}
        
    except Exception as e:
        return {"success": False, "domain": domain, "error": str(e)}


def get_scan_results():
    """Return current scan results."""
    return scan_results


def get_scan_status():
    """Return current scan status."""
    return scan_status


def get_current_user():
    """Return current user info."""
    return current_user


# ============== Mark as Read Functions ==============

mark_read_status = {"progress": 0, "message": "Ready", "done": False, "error": None, "marked": 0}

def get_unread_count():
    """Get count of unread emails."""
    service, error = get_gmail_service()
    if error:
        return {"error": error}
    
    try:
        # Get unread count
        results = service.users().messages().list(
            userId='me',
            q='is:unread',
            maxResults=1
        ).execute()
        
        # Estimate total (Gmail doesn't give exact count easily)
        total = results.get('resultSizeEstimate', 0)
        return {"count": total}
    except Exception as e:
        return {"error": str(e)}


def mark_emails_as_read(count=100):
    """Mark specified number of emails as read."""
    global mark_read_status
    
    mark_read_status = {"progress": 0, "message": "Connecting...", "done": False, "error": None, "marked": 0}
    
    service, error = get_gmail_service()
    if error:
        mark_read_status = {"progress": 0, "message": "", "done": True, "error": error, "marked": 0}
        return
    
    try:
        mark_read_status["message"] = f"Fetching unread emails..."
        
        # Get unread message IDs
        message_ids = []
        page_token = None
        
        while len(message_ids) < count:
            result = service.users().messages().list(
                userId='me',
                q='is:unread',
                maxResults=min(500, count - len(message_ids)),
                pageToken=page_token
            ).execute()
            
            messages = result.get('messages', [])
            if not messages:
                break
            message_ids.extend([m['id'] for m in messages])
            
            page_token = result.get('nextPageToken')
            if not page_token:
                break
        
        if not message_ids:
            mark_read_status = {"progress": 100, "message": "No unread emails found!", "done": True, "error": None, "marked": 0}
            return
        
        total = len(message_ids)
        mark_read_status["message"] = f"Marking {total} emails as read..."
        
        # Mark as read in batches using batchModify
        batch_size = 1000  # Gmail allows up to 1000 per batch
        marked = 0
        
        for i in range(0, len(message_ids), batch_size):
            batch_ids = message_ids[i:i + batch_size]
            
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': batch_ids,
                    'removeLabelIds': ['UNREAD']
                }
            ).execute()
            
            marked += len(batch_ids)
            progress = int(marked / total * 100)
            mark_read_status["progress"] = progress
            mark_read_status["message"] = f"Marked {marked}/{total} as read..."
            mark_read_status["marked"] = marked
        
        mark_read_status = {
            "progress": 100,
            "message": f"Done! Marked {marked} emails as read.",
            "done": True,
            "error": None,
            "marked": marked
        }
        
    except Exception as e:
        mark_read_status = {"progress": 0, "message": "", "done": True, "error": str(e), "marked": 0}


def get_mark_read_status():
    """Return current mark as read status."""
    return mark_read_status


# ============== Delete Emails Functions ==============

delete_scan_results = []
delete_scan_status = {"progress": 0, "message": "Ready", "done": False, "error": None}
delete_status = {"progress": 0, "message": "Ready", "done": False, "error": None, "deleted": 0}


def scan_senders_for_delete(limit=1000):
    """Scan emails and group by sender for deletion."""
    global delete_scan_results, delete_scan_status
    
    delete_scan_status = {"progress": 0, "message": "Connecting to Gmail...", "done": False, "error": None}
    delete_scan_results = []
    
    service, error = get_gmail_service()
    if error:
        delete_scan_status = {"progress": 0, "message": "", "done": True, "error": error}
        return
    
    try:
        delete_scan_status["message"] = "Fetching email list..."
        
        # Get message IDs
        message_ids = []
        page_token = None
        
        while len(message_ids) < limit:
            result = service.users().messages().list(
                userId='me',
                maxResults=min(500, limit - len(message_ids)),
                pageToken=page_token
            ).execute()
            
            messages = result.get('messages', [])
            message_ids.extend([m['id'] for m in messages])
            
            page_token = result.get('nextPageToken')
            if not page_token:
                break
        
        if not message_ids:
            delete_scan_status = {"progress": 100, "message": "No emails found", "done": True, "error": None}
            return
        
        total = len(message_ids)
        delete_scan_status["message"] = f"Found {total} emails. Analyzing senders..."
        
        # Process in batches and group by sender
        sender_data = defaultdict(lambda: {"email": None, "count": 0, "subjects": [], "msg_ids": []})
        processed = 0
        batch_size = 100
        
        def process_message(request_id, response, exception):
            nonlocal processed
            processed += 1
            
            if exception:
                return
            
            msg_id = response.get('id')
            headers = response.get('payload', {}).get('headers', [])
            sender_email, domain = get_sender_info(headers)
            
            if sender_email:
                subject = get_subject(headers)
                sender_data[sender_email]["email"] = sender_email
                sender_data[sender_email]["domain"] = domain
                sender_data[sender_email]["count"] += 1
                sender_data[sender_email]["msg_ids"].append(msg_id)
                if len(sender_data[sender_email]["subjects"]) < 2:
                    sender_data[sender_email]["subjects"].append(subject)
        
        for i in range(0, len(message_ids), batch_size):
            batch_ids = message_ids[i:i + batch_size]
            batch = service.new_batch_http_request(callback=process_message)
            
            for msg_id in batch_ids:
                batch.add(
                    service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='metadata',
                        metadataHeaders=['From', 'Subject']
                    )
                )
            
            batch.execute()
            
            progress = int((i + len(batch_ids)) / total * 100)
            delete_scan_status["progress"] = progress
            delete_scan_status["message"] = f"Scanned {processed}/{total} emails ({len(sender_data)} senders)"
            
            # Rate limiting - small delay every 5 batches (500 emails)
            if (i // batch_size + 1) % 5 == 0:
                time.sleep(0.5)
        
        # Sort by count (highest first)
        sorted_results = sorted(
            [{"email": k, "domain": v["domain"], "count": v["count"], "subjects": v["subjects"], "msg_ids": v["msg_ids"]} 
             for k, v in sender_data.items()],
            key=lambda x: x["count"],
            reverse=True
        )
        
        delete_scan_results = sorted_results
        
        delete_scan_status = {
            "progress": 100,
            "message": f"Found {len(sorted_results)} senders. Select senders to delete their emails.",
            "done": True,
            "error": None
        }
        
    except Exception as e:
        delete_scan_status = {"progress": 0, "message": "", "done": True, "error": str(e)}


def delete_emails_by_sender(sender_email):
    """Delete all emails from a specific sender - with rate limiting."""
    global delete_scan_results
    
    service, error = get_gmail_service()
    if error:
        return {"success": False, "error": error}
    
    # Find sender in results
    sender_data = None
    sender_index = None
    for i, item in enumerate(delete_scan_results):
        if item["email"] == sender_email:
            sender_data = item
            sender_index = i
            break
    
    if not sender_data:
        return {"success": False, "error": "Sender not found in scan results"}
    
    try:
        msg_ids = sender_data["msg_ids"]
        total = len(msg_ids)
        deleted = 0
        
        # Process in chunks of 500 (safer for rate limits)
        chunk_size = 500
        
        for i in range(0, len(msg_ids), chunk_size):
            batch_ids = msg_ids[i:i + chunk_size]
            
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': batch_ids,
                    'addLabelIds': ['TRASH']
                }
            ).execute()
            
            deleted += len(batch_ids)
            
            # Rate limiting - wait 1 second between batches
            if i + chunk_size < len(msg_ids):
                time.sleep(1)
        
        # Remove from results immediately
        delete_scan_results = [r for r in delete_scan_results if r["email"] != sender_email]
        
        return {
            "success": True,
            "deleted": deleted,
            "sender": sender_email,
            "message": f"Moved {deleted} emails to trash"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_emails_bulk(sender_emails):
    """Delete emails from multiple senders - with rate limiting."""
    global delete_scan_results
    
    service, error = get_gmail_service()
    if error:
        return {"success": False, "error": error}
    
    # Collect all message IDs from selected senders
    all_msg_ids = []
    senders_found = []
    
    for sender_email in sender_emails:
        for item in delete_scan_results:
            if item["email"] == sender_email:
                all_msg_ids.extend(item["msg_ids"])
                senders_found.append(sender_email)
                break
    
    if not all_msg_ids:
        return {"success": False, "error": "No emails found for selected senders"}
    
    try:
        total = len(all_msg_ids)
        deleted = 0
        
        # Process in chunks of 500 with rate limiting
        chunk_size = 500
        
        for i in range(0, len(all_msg_ids), chunk_size):
            batch_ids = all_msg_ids[i:i + chunk_size]
            
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': batch_ids,
                    'addLabelIds': ['TRASH']
                }
            ).execute()
            
            deleted += len(batch_ids)
            
            # Rate limiting - wait 1 second between batches
            if i + chunk_size < len(all_msg_ids):
                time.sleep(1)
        
        # Remove all deleted senders from results
        delete_scan_results = [r for r in delete_scan_results if r["email"] not in senders_found]
        
        return {
            "success": True,
            "deleted": deleted,
            "senders": len(senders_found),
            "message": f"Moved {deleted} emails from {len(senders_found)} senders to trash"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_delete_scan_results():
    """Return current delete scan results."""
    return delete_scan_results


def get_delete_scan_status():
    """Return current delete scan status."""
    return delete_scan_status
