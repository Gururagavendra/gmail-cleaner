"""
Gmail Service
-------------
Core Gmail operations: scanning, unsubscribing, marking read, deleting.
"""

import re
import time
import urllib.request
import ssl
import socket
import ipaddress
from urllib.parse import urlparse
from collections import defaultdict
from typing import Optional, Union, Any

from app.core import state
from app.services.auth import get_gmail_service


# ----- Security Helpers -----

def _validate_unsafe_url(url: str) -> str:
    """
    Validate URL to prevent SSRF.
    Checks scheme and resolves hostname to ensure it's not a local/private IP.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError("Invalid URL format")
    
    if parsed.scheme not in ('http', 'https'):
        raise ValueError("Invalid URL scheme. Only HTTP and HTTPS are allowed.")
    
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: No hostname found.")
    
    # Resolve hostname to IP
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
    except socket.gaierror:
        raise ValueError(f"Could not resolve hostname: {hostname}")
    except ValueError:
        raise ValueError(f"Invalid IP address resolved: {ip_str}")

    # Check for restricted IP ranges
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
         raise ValueError(f"Blocked restricted IP: {ip_str}")
         
    return url


# ----- Filters -----

def build_gmail_query(filters: Optional[Union[dict, Any]] = None) -> str:
    """Build Gmail search query from filter parameters.
    
    Args:
        filters: dict with keys:
            - older_than: '7d', '30d', '90d', '180d', '365d' or empty (for relative dates)
            - after_date: 'YYYY/MM/DD' for emails after this date
            - before_date: 'YYYY/MM/DD' for emails before this date
            - larger_than: '1M', '5M', '10M', '25M' or empty
            - category: 'promotions', 'social', 'updates', 'forums', 'primary' or empty
            - sender: 'email@domain.com' or 'domain.com' to filter by sender
    
    Returns:
        Gmail query string, empty string if no filters
    """
    if not filters:
        return ""
    
    # Handle both dict and Pydantic model
    if hasattr(filters, 'model_dump'):
        filters = filters.model_dump(exclude_none=True)
    
    query_parts = []
    
    # Use after/before dates if provided (custom date range)
    if after_date := filters.get('after_date', ''):
        query_parts.append(f'after:{after_date}')
    
    if before_date := filters.get('before_date', ''):
        query_parts.append(f'before:{before_date}')
    
    # Fall back to older_than for preset options
    if not after_date and not before_date:
        if older_than := filters.get('older_than', ''):
            query_parts.append(f'older_than:{older_than}')
    
    if larger_than := filters.get('larger_than', ''):
        query_parts.append(f'larger:{larger_than}')
    
    if category := filters.get('category', ''):
        query_parts.append(f'category:{category}')
    
    if sender := filters.get('sender', ''):
        query_parts.append(f'from:{sender}')
    
    if label := filters.get('label', ''):
        query_parts.append(f'label:{label}')
    
    return ' '.join(query_parts)


# ----- Email Parsing Helpers -----

def _get_unsubscribe_from_headers(headers: list) -> tuple[Optional[str], Optional[str]]:
    """Extract unsubscribe link from email headers."""
    for header in headers:
        if header['name'].lower() == 'list-unsubscribe':
            value = header['value']
            
            # Look for one-click POST header
            for h in headers:
                if h['name'].lower() == 'list-unsubscribe-post':
                    # Has one-click support
                    urls = re.findall(r'<(https?://[^>]+)>', value)
                    if urls:
                        return urls[0], "one-click"
            
            # Standard unsubscribe link
            urls = re.findall(r'<(https?://[^>]+)>', value)
            if urls:
                return urls[0], "manual"
            
            # mailto: link as fallback
            mailto = re.findall(r'<(mailto:[^>]+)>', value)
            if mailto:
                return mailto[0], "manual"
    
    return None, None


def _get_sender_info(headers: list) -> tuple[str, str]:
    """Extract sender name and email from headers."""
    for header in headers:
        if header['name'].lower() == 'from':
            from_value = header['value']
            match = re.search(r'([^<]*)<([^>]+)>', from_value)
            if match:
                name = match.group(1).strip().strip('"')
                email = match.group(2).strip()
                return name or email, email
            return from_value, from_value
    return "Unknown", "unknown"


def _get_subject(headers: list) -> str:
    """Extract subject from email headers."""
    for header in headers:
        if header['name'].lower() == 'subject':
            return header['value']
    return "(No Subject)"


# ----- Scanning -----

def scan_emails(limit: int = 500, filters: Optional[dict] = None):
    """Scan emails for unsubscribe links using Gmail Batch API."""
    state.reset_scan()
    state.scan_status["message"] = "Connecting to Gmail..."
    
    service, error = get_gmail_service()
    if error:
        state.scan_status["error"] = error
        state.scan_status["done"] = True
        return
    
    try:
        state.scan_status["message"] = "Fetching email list..."
        
        # Build query
        query = build_gmail_query(filters)
        
        # Get message IDs (fast - just IDs)
        message_ids = []
        page_token = None
        
        while len(message_ids) < limit:
            list_params = {
                'userId': 'me',
                'maxResults': min(500, limit - len(message_ids)),
            }
            if page_token:
                list_params['pageToken'] = page_token
            if query:  # Only add q parameter if query is not empty
                list_params['q'] = query
            
            result = service.users().messages().list(**list_params).execute()
            
            messages = result.get('messages', [])
            message_ids.extend([m['id'] for m in messages])
            
            page_token = result.get('nextPageToken')
            if not page_token:
                break
        
        if not message_ids:
            state.scan_status["message"] = "No emails found"
            state.scan_status["done"] = True
            return
        
        total = len(message_ids)
        state.scan_status["message"] = f"Found {total} emails. Scanning..."
        
        # Process in batches using Gmail Batch API (100 requests per HTTP call!)
        unsubscribe_data: dict[str, dict] = defaultdict(lambda: {
            "link": None, "count": 0, "subjects": [], "type": None, "sender": "", "email": "", "first_date": None, "last_date": None
        })
        processed = 0
        batch_size = 100
        
        def process_message(request_id, response, exception):
            nonlocal processed
            processed += 1
            
            if exception:
                return
            
            headers = response.get('payload', {}).get('headers', [])
            unsub_link, unsub_type = _get_unsubscribe_from_headers(headers)
            
            if unsub_link:
                sender_name, sender_email = _get_sender_info(headers)
                subject = _get_subject(headers)
                domain = sender_email.split('@')[-1] if '@' in sender_email else sender_email
                
                # Extract date from headers
                email_date = None
                for header in headers:
                    if header['name'].lower() == 'date':
                        email_date = header['value']
                        break
                
                unsubscribe_data[domain]["link"] = unsub_link
                unsubscribe_data[domain]["count"] += 1
                unsubscribe_data[domain]["type"] = unsub_type
                unsubscribe_data[domain]["sender"] = sender_name
                unsubscribe_data[domain]["email"] = sender_email
                if len(unsubscribe_data[domain]["subjects"]) < 3:
                    unsubscribe_data[domain]["subjects"].append(subject)
                
                # Track first and last dates
                if email_date:
                    if unsubscribe_data[domain]["first_date"] is None:
                        unsubscribe_data[domain]["first_date"] = email_date
                    unsubscribe_data[domain]["last_date"] = email_date
        
        # Execute batch requests
        for i in range(0, len(message_ids), batch_size):
            batch_ids = message_ids[i:i + batch_size]
            batch = service.new_batch_http_request(callback=process_message)
            
            for msg_id in batch_ids:
                batch.add(
                    service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='metadata',
                        metadataHeaders=['From', 'Subject', 'Date', 'List-Unsubscribe', 'List-Unsubscribe-Post']
                    )
                )
            
            batch.execute()
            
            progress = int((i + len(batch_ids)) / total * 100)
            state.scan_status["progress"] = progress
            state.scan_status["message"] = f"Scanned {processed}/{total} emails ({len(unsubscribe_data)} found)"
            
            # Rate limiting - small delay every 5 batches (500 emails)
            if (i // batch_size + 1) % 5 == 0:
                time.sleep(0.3)
        
        # Sort by count and format results
        sorted_results = sorted(
            [{"domain": k, "link": v["link"], "count": v["count"], "subjects": v["subjects"], 
              "type": v["type"], "sender": v.get("sender", ""), "email": v.get("email", ""), 
              "first_date": v.get("first_date"), "last_date": v.get("last_date")} 
             for k, v in unsubscribe_data.items()],
            key=lambda x: x["count"],
            reverse=True
        )
        
        state.scan_results = sorted_results
        state.scan_status["message"] = f"Found {len(state.scan_results)} subscriptions"
        state.scan_status["done"] = True
        
    except Exception as e:
        state.scan_status["error"] = str(e)
        state.scan_status["done"] = True


def get_scan_status() -> dict:
    """Get current scan status."""
    return state.scan_status.copy()


def get_scan_results() -> list:
    """Get scan results."""
    return state.scan_results.copy()


# ----- Unsubscribe -----

def unsubscribe_single(domain: str, link: str) -> dict:
    """Attempt to unsubscribe from a single sender."""
    if not link:
        return {"success": False, "message": "No unsubscribe link provided"}
    
    # Handle mailto: links
    if link.startswith('mailto:'):
        return {
            "success": False,
            "message": "Email-based unsubscribe - open in email client",
            "type": "mailto"
        }
    
    try:
        # Validate URL for SSRF (Check scheme and block private/loopback IPs)
        try:
            link = _validate_unsafe_url(link)
        except ValueError as e:
            return {"success": False, "message": f"Security Error: {str(e)}"}

        # Create Default SSL context (Verifies certs by default)
        # We removed the custom context that disabled verification.
        
        # Try POST first (one-click), then GET
        req = urllib.request.Request(
            link,
            data=b'List-Unsubscribe=One-Click',
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; GmailUnsubscribe/1.0)',
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            method='POST'
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in [200, 201, 202, 204]:
                    return {"success": True, "message": "Unsubscribed successfully", "domain": domain}
        except Exception:
            pass
        
        # Fallback to GET
        req = urllib.request.Request(
            link,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; GmailUnsubscribe/1.0)'}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status in [200, 201, 202, 204, 301, 302]:
                return {"success": True, "message": "Unsubscribed (confirmation may be needed)", "domain": domain}
        
        return {"success": False, "message": f"Server returned status {response.status}"}
        
    except Exception as e:
        return {"success": False, "message": str(e)[:100]}


# ----- Mark as Read -----

def get_unread_count() -> dict:
    """Get count of unread emails in Inbox."""
    service, error = get_gmail_service()
    if error:
        return {"count": 0, "error": error}
    
    try:
        # Simply count unread messages - query and count actual results
        results = service.users().messages().list(
            userId='me',
            q='is:unread in:inbox',
            maxResults=500
        ).execute()
        
        messages = results.get('messages', [])
        count = len(messages)
        
        # Check if there are more
        if results.get('nextPageToken'):
            count = f"{count}+"
        
        return {"count": count}
    except Exception as e:
        return {"count": 0, "error": str(e)}


def mark_emails_as_read(count: int = 100, filters: Optional[dict] = None):
    """Mark unread emails as read."""
    state.reset_mark_read()
    state.mark_read_status["message"] = "Connecting to Gmail..."
    
    service, error = get_gmail_service()
    if error:
        state.mark_read_status["error"] = error
        state.mark_read_status["done"] = True
        return
    
    try:
        state.mark_read_status["message"] = "Finding unread emails..."
        
        # Build query
        query = 'is:unread'
        if filter_query := build_gmail_query(filters):
            query = f'{query} {filter_query}'
        
        # Fetch unread messages
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=min(count, 500)
        ).execute()
        
        messages = results.get('messages', [])
        
        # Pagination
        while 'nextPageToken' in results and len(messages) < count:
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=min(count - len(messages), 500),
                pageToken=results['nextPageToken']
            ).execute()
            messages.extend(results.get('messages', []))
        
        messages = messages[:count]
        total = len(messages)
        
        if total == 0:
            state.mark_read_status["message"] = "No unread emails found"
            state.mark_read_status["done"] = True
            return
        
        # Batch mark as read
        batch_size = 100
        marked = 0
        
        for i in range(0, total, batch_size):
            batch = messages[i:i + batch_size]
            ids = [msg['id'] for msg in batch]
            
            service.users().messages().batchModify(
                userId='me',
                body={'ids': ids, 'removeLabelIds': ['UNREAD']}
            ).execute()
            
            marked += len(ids)
            progress = int(marked / total * 100)
            state.mark_read_status["progress"] = progress
            state.mark_read_status["message"] = f"Marked {marked}/{total} as read"
            state.mark_read_status["marked_count"] = marked
        
        state.mark_read_status["message"] = f"Done! Marked {marked} emails as read"
        state.mark_read_status["done"] = True
        
    except Exception as e:
        state.mark_read_status["error"] = str(e)
        state.mark_read_status["done"] = True


def get_mark_read_status() -> dict:
    """Get mark-as-read status."""
    return state.mark_read_status.copy()


# ----- Delete -----

def scan_senders_for_delete(limit: int = 1000, filters: Optional[dict] = None):
    """Scan emails and group by sender for bulk delete."""
    state.reset_delete_scan()
    state.delete_scan_status["message"] = "Connecting to Gmail..."
    
    service, error = get_gmail_service()
    if error:
        state.delete_scan_status["error"] = error
        state.delete_scan_status["done"] = True
        return
    
    try:
        state.delete_scan_status["message"] = "Fetching emails..."
        
        query = build_gmail_query(filters)
        
        results = service.users().messages().list(
            userId='me',
            maxResults=min(limit, 500),
            q=query or None
        ).execute()
        
        messages = results.get('messages', [])
        
        while 'nextPageToken' in results and len(messages) < limit:
            results = service.users().messages().list(
                userId='me',
                maxResults=min(limit - len(messages), 500),
                pageToken=results['nextPageToken'],
                q=query or None
            ).execute()
            messages.extend(results.get('messages', []))
        
        messages = messages[:limit]
        total = len(messages)
        
        if total == 0:
            state.delete_scan_status["message"] = "No emails found"
            state.delete_scan_status["done"] = True
            return
        
        state.delete_scan_status["message"] = f"Scanning {total} emails..."
        
        # Group by sender using Gmail Batch API
        sender_counts: dict[str, dict] = defaultdict(lambda: {"count": 0, "sender": "", "email": "", "subjects": [], "first_date": None, "last_date": None, "message_ids": [], "total_size": 0})
        processed = 0
        batch_size = 100
        
        def process_message(request_id, response, exception):
            nonlocal processed
            processed += 1
            
            if exception:
                return
            
            headers = response.get('payload', {}).get('headers', [])
            sender_name, sender_email = _get_sender_info(headers)
            subject = _get_subject(headers)
            msg_id = response.get('id', '')
            size_estimate = response.get('sizeEstimate', 0)
            
            # Extract date from headers
            email_date = None
            for header in headers:
                if header['name'].lower() == 'date':
                    email_date = header['value']
                    break
            
            if sender_email:
                sender_counts[sender_email]["count"] += 1
                sender_counts[sender_email]["sender"] = sender_name
                sender_counts[sender_email]["email"] = sender_email
                sender_counts[sender_email]["message_ids"].append(msg_id)
                sender_counts[sender_email]["total_size"] += size_estimate
                if len(sender_counts[sender_email]["subjects"]) < 3:
                    sender_counts[sender_email]["subjects"].append(subject)
                
                # Track first and last dates
                if email_date:
                    if sender_counts[sender_email]["first_date"] is None:
                        sender_counts[sender_email]["first_date"] = email_date
                    sender_counts[sender_email]["last_date"] = email_date
        
        # Execute batch requests
        for i in range(0, len(messages), batch_size):
            batch_ids = messages[i:i + batch_size]
            batch = service.new_batch_http_request(callback=process_message)
            
            for msg_data in batch_ids:
                batch.add(
                    service.users().messages().get(
                        userId='me',
                        id=msg_data['id'],
                        format='metadata',
                        metadataHeaders=['From', 'Subject', 'Date']
                    )
                )
            
            batch.execute()
            
            progress = int((i + len(batch_ids)) / total * 100)
            state.delete_scan_status["progress"] = progress
            state.delete_scan_status["message"] = f"Scanned {processed}/{total} emails"
            
            # Rate limiting
            if (i // batch_size + 1) % 5 == 0:
                time.sleep(0.3)
        
        # Sort by count
        sorted_senders = sorted(
            [{"email": k, **v} for k, v in sender_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )
        
        state.delete_scan_results = sorted_senders
        state.delete_scan_status["message"] = f"Found {len(sorted_senders)} senders"
        state.delete_scan_status["done"] = True
        
    except Exception as e:
        state.delete_scan_status["error"] = str(e)
        state.delete_scan_status["done"] = True


def get_delete_scan_status() -> dict:
    """Get delete scan status."""
    return state.delete_scan_status.copy()


def get_delete_scan_results() -> list:
    """Get delete scan results."""
    return state.delete_scan_results.copy()


def delete_emails_by_sender(sender: str) -> dict:
    """Delete all emails from a specific sender."""
    if not sender:
        return {"success": False, "deleted": 0, "size_freed": 0, "message": "No sender specified"}
    
    # Get size info from cached results before deleting
    size_freed = 0
    for r in state.delete_scan_results:
        if r.get("email") == sender:
            size_freed = r.get("total_size", 0)
            break
    
    service, error = get_gmail_service()
    if error:
        return {"success": False, "deleted": 0, "size_freed": 0, "message": error}
    
    try:
        # Find all emails from sender
        query = f'from:{sender}'
        results = service.users().messages().list(userId='me', q=query, maxResults=500).execute()
        messages = results.get('messages', [])
        
        while 'nextPageToken' in results:
            results = service.users().messages().list(
                userId='me', q=query, maxResults=500, pageToken=results['nextPageToken']
            ).execute()
            messages.extend(results.get('messages', []))
        
        if not messages:
            return {"success": True, "deleted": 0, "size_freed": 0, "message": "No emails found"}
        
        # Batch delete (move to trash)
        ids = [msg['id'] for msg in messages]
        batch_size = 100
        deleted = 0
        
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            service.users().messages().batchModify(
                userId='me',
                body={'ids': batch, 'addLabelIds': ['TRASH']}
            ).execute()
            deleted += len(batch)
        
        # Remove sender from cached results
        state.delete_scan_results = [
            r for r in state.delete_scan_results 
            if r.get("email") != sender
        ]
        
        return {"success": True, "deleted": deleted, "size_freed": size_freed, "message": f"Moved {deleted} emails to trash"}
        
    except Exception as e:
        return {"success": False, "deleted": 0, "size_freed": 0, "message": str(e)}


def delete_emails_bulk(senders: list[str]) -> dict:
    """Delete emails from multiple senders."""
    if not senders:
        return {"success": False, "deleted": 0, "size_freed": 0, "message": "No senders specified"}
    
    total_deleted = 0
    total_size_freed = 0
    errors = []
    
    for sender in senders:
        result = delete_emails_by_sender(sender)
        if result["success"]:
            total_deleted += result["deleted"]
            total_size_freed += result.get("size_freed", 0)
        else:
            errors.append(f"{sender}: {result['message']}")
    
    # Note: delete_emails_by_sender already removes each sender from cached results
    
    if errors:
        return {
            "success": len(errors) < len(senders),
            "deleted": total_deleted,
            "size_freed": total_size_freed,
            "message": f"Deleted {total_deleted} emails. Errors: {'; '.join(errors[:3])}"
        }
    
    if total_deleted == 0:
        return {"success": False, "deleted": 0, "size_freed": 0, "message": "No emails found to delete"}
    return {"success": True, "deleted": total_deleted, "size_freed": total_size_freed, "message": f"Deleted {total_deleted} emails"}


# ----- Download Emails Functions -----

def download_emails_background(senders: list[str]) -> None:
    """Download email metadata for selected senders as CSV (background task).
    
    Uses message IDs stored during scan to download only scanned emails.
    """
    import csv
    import io
    import base64
    
    state.reset_download()
    
    if not senders:
        state.download_status["done"] = True
        state.download_status["error"] = "No senders specified"
        return
    
    service, error = get_gmail_service()
    if error:
        state.download_status["done"] = True
        state.download_status["error"] = error
        return
    
    state.download_status["message"] = "Collecting emails from scan results..."
    
    # Get message IDs from scan results (only emails we actually scanned)
    all_message_ids = []
    for sender in senders:
        for result in state.delete_scan_results:
            if result.get("email") == sender:
                all_message_ids.extend(result.get("message_ids", []))
                break
    
    if not all_message_ids:
        state.download_status["progress"] = 100
        state.download_status["done"] = True
        state.download_status["error"] = "No emails found in scan results"
        return
    
    total_emails = len(all_message_ids)
    state.download_status["total_emails"] = total_emails
    state.download_status["message"] = f"Fetching {total_emails} emails..."
    
    # Helper to decode base64 email content
    def decode_base64_content(data: str) -> str:
        """Decode base64 URL-safe encoded email content."""
        return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    
    # Helper function to extract email body
    def get_email_body(payload):
        """Extract email body from payload. Prefers text/plain over text/html."""
        body = ""
        
        if 'body' in payload and payload['body'].get('data'):
            body = decode_base64_content(payload['body']['data'])
        elif 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                if mime_type == 'text/plain':
                    if 'body' in part and part['body'].get('data'):
                        body = decode_base64_content(part['body']['data'])
                        break
                elif mime_type == 'text/html' and not body:
                    if 'body' in part and part['body'].get('data'):
                        body = decode_base64_content(part['body']['data'])
                elif 'parts' in part:
                    body = get_email_body(part)
                    if body:
                        break
        
        return body.strip()
    
    # Fetch full email content in batches
    email_data = []
    batch_size = 50  # Smaller batches for full content
    fetched = 0
    
    try:
        for i in range(0, total_emails, batch_size):
            batch_ids = all_message_ids[i:i + batch_size]
            
            batch = service.new_batch_http_request()
            batch_results = []
            
            def callback(request_id, response, exception):
                if exception is None and response:
                    batch_results.append(response)
            
            for msg_id in batch_ids:
                batch.add(
                    service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='full'
                    ),
                    callback=callback
                )
            
            batch.execute()
            
            # Process batch results
            for msg in batch_results:
                headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
                body = get_email_body(msg.get('payload', {}))
                
                email_data.append({
                    'message_id': msg.get('id', ''),
                    'thread_id': msg.get('threadId', ''),
                    'from': headers.get('From', ''),
                    'subject': headers.get('Subject', ''),
                    'date': headers.get('Date', ''),
                    'labels': ', '.join(msg.get('labelIds', [])),
                    'snippet': msg.get('snippet', '')[:100],
                    'body': body[:50000] if body else ''  # Limit to 50,000 characters
                })
            
            fetched += len(batch_ids)
            state.download_status["fetched_count"] = fetched
            state.download_status["progress"] = int((fetched / total_emails) * 95)
            state.download_status["message"] = f"Fetched {fetched}/{total_emails} emails..."
    
    except Exception as e:
        state.download_status["done"] = True
        state.download_status["error"] = f"Error fetching emails: {str(e)}"
        return
    
    # Generate CSV
    state.download_status["progress"] = 98
    state.download_status["message"] = "Generating CSV..."
    
    try:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['message_id', 'thread_id', 'from', 'subject', 'date', 'labels', 'snippet', 'body'])
        writer.writeheader()
        writer.writerows(email_data)
        
        state.download_status["csv_data"] = output.getvalue()
        state.download_status["progress"] = 100
        state.download_status["done"] = True
        state.download_status["message"] = f"Ready to download {len(email_data)} emails"
    
    except Exception as e:
        state.download_status["done"] = True
        state.download_status["error"] = f"Error generating CSV: {str(e)}"


def get_download_status() -> dict:
    """Get download operation status (without CSV data)."""
    return {
        "progress": state.download_status["progress"],
        "message": state.download_status["message"],
        "done": state.download_status["done"],
        "error": state.download_status["error"],
        "total_emails": state.download_status["total_emails"],
        "fetched_count": state.download_status["fetched_count"]
    }


def get_download_csv() -> str | None:
    """Get the generated CSV data."""
    return state.download_status.get("csv_data")


def delete_emails_bulk_background(senders: list[str]) -> None:
    """Delete emails from multiple senders with progress updates (background task).
    
    Optimized to collect all message IDs first, then batch delete in larger chunks.
    """
    from app.core import state
    
    state.reset_delete_bulk()
    
    if not senders:
        state.delete_bulk_status["done"] = True
        state.delete_bulk_status["error"] = "No senders specified"
        return
    
    total_senders = len(senders)
    state.delete_bulk_status["total_senders"] = total_senders
    state.delete_bulk_status["message"] = "Collecting emails to delete..."
    
    service, error = get_gmail_service()
    if error:
        state.delete_bulk_status["done"] = True
        state.delete_bulk_status["error"] = error
        return
    
    # Phase 1: Collect all message IDs from all senders
    all_message_ids = []
    errors = []
    
    for i, sender in enumerate(senders):
        state.delete_bulk_status["current_sender"] = i + 1
        state.delete_bulk_status["progress"] = int((i / total_senders) * 40)  # 0-40% for collecting
        state.delete_bulk_status["message"] = f"Finding emails from {sender}..."
        
        try:
            query = f'from:{sender}'
            results = service.users().messages().list(userId='me', q=query, maxResults=500).execute()
            messages = results.get('messages', [])
            
            while 'nextPageToken' in results:
                results = service.users().messages().list(
                    userId='me', q=query, maxResults=500, pageToken=results['nextPageToken']
                ).execute()
                messages.extend(results.get('messages', []))
            
            all_message_ids.extend([msg['id'] for msg in messages])
        except Exception as e:
            errors.append(f"{sender}: {str(e)}")
    
    if not all_message_ids:
        state.delete_bulk_status["progress"] = 100
        state.delete_bulk_status["done"] = True
        state.delete_bulk_status["message"] = "No emails found to delete"
        return
    
    # Phase 2: Batch delete all collected IDs (larger batches = fewer API calls)
    total_emails = len(all_message_ids)
    state.delete_bulk_status["message"] = f"Deleting {total_emails} emails..."
    
    batch_size = 1000  # Gmail allows up to 1000 per batchModify
    deleted = 0
    
    try:
        for i in range(0, total_emails, batch_size):
            batch = all_message_ids[i:i + batch_size]
            service.users().messages().batchModify(
                userId='me',
                body={'ids': batch, 'addLabelIds': ['TRASH']}
            ).execute()
            deleted += len(batch)
            state.delete_bulk_status["deleted_count"] = deleted
            # Progress: 40-100% for deleting
            state.delete_bulk_status["progress"] = 40 + int((deleted / total_emails) * 60)
            state.delete_bulk_status["message"] = f"Deleted {deleted}/{total_emails} emails..."
    except Exception as e:
        errors.append(f"Batch delete error: {str(e)}")
    
    # Remove deleted senders from cached scan results
    state.delete_scan_results = [
        r for r in state.delete_scan_results
        if r.get("email") not in senders
    ]
    
    # Done
    state.delete_bulk_status["progress"] = 100
    state.delete_bulk_status["done"] = True
    state.delete_bulk_status["deleted_count"] = deleted
    
    if errors:
        state.delete_bulk_status["error"] = f"Some errors: {'; '.join(errors[:3])}"
        state.delete_bulk_status["message"] = f"Deleted {deleted} emails with some errors"
    else:
        state.delete_bulk_status["message"] = f"Successfully deleted {deleted} emails"


def get_delete_bulk_status() -> dict:
    """Get delete bulk operation status."""
    from app.core import state
    return state.delete_bulk_status


# ----- Label Management Functions -----

def get_labels() -> dict:
    """Get all Gmail labels."""
    service, error = get_gmail_service()
    if error:
        return {"success": False, "labels": [], "error": error}
    
    try:
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        
        # Categorize labels
        system_labels = []
        user_labels = []
        
        for label in labels:
            label_info = {
                "id": label.get('id'),
                "name": label.get('name'),
                "type": label.get('type', 'user')
            }
            
            if label.get('type') == 'system':
                system_labels.append(label_info)
            else:
                user_labels.append(label_info)
        
        # Sort user labels alphabetically
        user_labels.sort(key=lambda x: x['name'].lower())
        
        return {
            "success": True,
            "system_labels": system_labels,
            "user_labels": user_labels,
            "error": None
        }
    except Exception as e:
        return {"success": False, "labels": [], "error": str(e)}


def create_label(name: str) -> dict:
    """Create a new Gmail label."""
    if not name or not name.strip():
        return {"success": False, "label": None, "error": "Label name is required"}
    
    service, error = get_gmail_service()
    if error:
        return {"success": False, "label": None, "error": error}
    
    try:
        label_body = {
            'name': name.strip(),
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
        
        result = service.users().labels().create(userId='me', body=label_body).execute()
        
        return {
            "success": True,
            "label": {
                "id": result.get('id'),
                "name": result.get('name'),
                "type": result.get('type', 'user')
            },
            "error": None
        }
    except Exception as e:
        error_msg = str(e)
        if 'Label name exists' in error_msg or 'already exists' in error_msg.lower():
            return {"success": False, "label": None, "error": "A label with this name already exists"}
        return {"success": False, "label": None, "error": error_msg}


def delete_label(label_id: str) -> dict:
    """Delete a Gmail label."""
    if not label_id:
        return {"success": False, "error": "Label ID is required"}
    
    service, error = get_gmail_service()
    if error:
        return {"success": False, "error": error}
    
    try:
        service.users().labels().delete(userId='me', id=label_id).execute()
        return {"success": True, "error": None}
    except Exception as e:
        error_msg = str(e)
        if 'Not Found' in error_msg:
            return {"success": False, "error": "Label not found"}
        if 'Cannot delete' in error_msg or 'system label' in error_msg.lower():
            return {"success": False, "error": "Cannot delete system labels"}
        return {"success": False, "error": error_msg}


def apply_label_to_senders_background(label_id: str, senders: list[str]) -> None:
    """Apply a label to all emails from specified senders (background task)."""
    state.reset_label_operation()
    
    if not label_id:
        state.label_operation_status["done"] = True
        state.label_operation_status["error"] = "Label ID is required"
        return
    
    if not senders:
        state.label_operation_status["done"] = True
        state.label_operation_status["error"] = "No senders specified"
        return
    
    service, error = get_gmail_service()
    if error:
        state.label_operation_status["done"] = True
        state.label_operation_status["error"] = error
        return
    
    total_senders = len(senders)
    state.label_operation_status["total_senders"] = total_senders
    state.label_operation_status["message"] = "Finding emails to label..."
    
    # Phase 1: Collect all message IDs
    all_message_ids = []
    errors = []
    
    for i, sender in enumerate(senders):
        state.label_operation_status["current_sender"] = i + 1
        state.label_operation_status["progress"] = int((i / total_senders) * 40)
        state.label_operation_status["message"] = f"Finding emails from {sender}..."
        
        try:
            query = f'from:{sender}'
            results = service.users().messages().list(userId='me', q=query, maxResults=500).execute()
            messages = results.get('messages', [])
            
            while 'nextPageToken' in results:
                results = service.users().messages().list(
                    userId='me', q=query, maxResults=500, pageToken=results['nextPageToken']
                ).execute()
                messages.extend(results.get('messages', []))
            
            all_message_ids.extend([msg['id'] for msg in messages])
        except Exception as e:
            errors.append(f"{sender}: {str(e)}")
    
    if not all_message_ids:
        state.label_operation_status["progress"] = 100
        state.label_operation_status["done"] = True
        state.label_operation_status["message"] = "No emails found to label"
        return
    
    # Phase 2: Apply label in batches
    total_emails = len(all_message_ids)
    state.label_operation_status["message"] = f"Applying label to {total_emails} emails..."
    
    batch_size = 1000
    labeled = 0
    
    try:
        for i in range(0, total_emails, batch_size):
            batch = all_message_ids[i:i + batch_size]
            service.users().messages().batchModify(
                userId='me',
                body={'ids': batch, 'addLabelIds': [label_id]}
            ).execute()
            labeled += len(batch)
            state.label_operation_status["affected_count"] = labeled
            state.label_operation_status["progress"] = 40 + int((labeled / total_emails) * 60)
            state.label_operation_status["message"] = f"Labeled {labeled}/{total_emails} emails..."
    except Exception as e:
        errors.append(f"Batch label error: {str(e)}")
    
    # Done
    state.label_operation_status["progress"] = 100
    state.label_operation_status["done"] = True
    state.label_operation_status["affected_count"] = labeled
    
    if errors:
        state.label_operation_status["error"] = f"Some errors: {'; '.join(errors[:3])}"
        state.label_operation_status["message"] = f"Labeled {labeled} emails with some errors"
    else:
        state.label_operation_status["message"] = f"Successfully labeled {labeled} emails"


def remove_label_from_senders_background(label_id: str, senders: list[str]) -> None:
    """Remove a label from all emails from specified senders (background task)."""
    state.reset_label_operation()
    
    if not label_id:
        state.label_operation_status["done"] = True
        state.label_operation_status["error"] = "Label ID is required"
        return
    
    if not senders:
        state.label_operation_status["done"] = True
        state.label_operation_status["error"] = "No senders specified"
        return
    
    service, error = get_gmail_service()
    if error:
        state.label_operation_status["done"] = True
        state.label_operation_status["error"] = error
        return
    
    total_senders = len(senders)
    state.label_operation_status["total_senders"] = total_senders
    state.label_operation_status["message"] = "Finding emails to unlabel..."
    
    # Phase 1: Collect all message IDs that have this label
    all_message_ids = []
    errors = []
    
    for i, sender in enumerate(senders):
        state.label_operation_status["current_sender"] = i + 1
        state.label_operation_status["progress"] = int((i / total_senders) * 40)
        state.label_operation_status["message"] = f"Finding emails from {sender}..."
        
        try:
            # Search for emails from sender that have this label
            query = f'from:{sender} label:{label_id}'
            results = service.users().messages().list(userId='me', q=query, maxResults=500).execute()
            messages = results.get('messages', [])
            
            while 'nextPageToken' in results:
                results = service.users().messages().list(
                    userId='me', q=query, maxResults=500, pageToken=results['nextPageToken']
                ).execute()
                messages.extend(results.get('messages', []))
            
            all_message_ids.extend([msg['id'] for msg in messages])
        except Exception as e:
            errors.append(f"{sender}: {str(e)}")
    
    if not all_message_ids:
        state.label_operation_status["progress"] = 100
        state.label_operation_status["done"] = True
        state.label_operation_status["message"] = "No emails found with this label"
        return
    
    # Phase 2: Remove label in batches
    total_emails = len(all_message_ids)
    state.label_operation_status["message"] = f"Removing label from {total_emails} emails..."
    
    batch_size = 1000
    unlabeled = 0
    
    try:
        for i in range(0, total_emails, batch_size):
            batch = all_message_ids[i:i + batch_size]
            service.users().messages().batchModify(
                userId='me',
                body={'ids': batch, 'removeLabelIds': [label_id]}
            ).execute()
            unlabeled += len(batch)
            state.label_operation_status["affected_count"] = unlabeled
            state.label_operation_status["progress"] = 40 + int((unlabeled / total_emails) * 60)
            state.label_operation_status["message"] = f"Unlabeled {unlabeled}/{total_emails} emails..."
    except Exception as e:
        errors.append(f"Batch unlabel error: {str(e)}")
    
    # Done
    state.label_operation_status["progress"] = 100
    state.label_operation_status["done"] = True
    state.label_operation_status["affected_count"] = unlabeled
    
    if errors:
        state.label_operation_status["error"] = f"Some errors: {'; '.join(errors[:3])}"
        state.label_operation_status["message"] = f"Unlabeled {unlabeled} emails with some errors"
    else:
        state.label_operation_status["message"] = f"Successfully removed label from {unlabeled} emails"


def get_label_operation_status() -> dict:
    """Get label operation status."""
    return state.label_operation_status.copy()


# ----- Archive Functions -----

def archive_emails_background(senders: list[str]):
    """Archive emails from selected senders (remove INBOX label)."""
    state.reset_archive()
    state.archive_status["total_senders"] = len(senders)
    state.archive_status["message"] = "Starting archive..."
    
    try:
        service = get_gmail_service()
        if not service:
            state.archive_status["error"] = "Not authenticated"
            state.archive_status["done"] = True
            return
        
        total_archived = 0
        
        for i, sender in enumerate(senders):
            state.archive_status["current_sender"] = i + 1
            state.archive_status["message"] = f"Archiving emails from {sender}..."
            state.archive_status["progress"] = int((i / len(senders)) * 100)
            
            # Find all emails from this sender in INBOX
            query = f"from:{sender} in:inbox"
            message_ids = []
            page_token = None
            
            while True:
                result = service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=500,
                    pageToken=page_token
                ).execute()
                
                messages = result.get('messages', [])
                message_ids.extend([m['id'] for m in messages])
                
                page_token = result.get('nextPageToken')
                if not page_token:
                    break
            
            if not message_ids:
                continue
            
            # Archive in batches (remove INBOX label)
            for j in range(0, len(message_ids), 100):
                batch_ids = message_ids[j:j+100]
                service.users().messages().batchModify(
                    userId='me',
                    body={
                        'ids': batch_ids,
                        'removeLabelIds': ['INBOX']
                    }
                ).execute()
                total_archived += len(batch_ids)
                
                if j > 0 and j % 500 == 0:
                    import time
                    time.sleep(0.5)
        
        state.archive_status["progress"] = 100
        state.archive_status["done"] = True
        state.archive_status["archived_count"] = total_archived
        state.archive_status["message"] = f"Archived {total_archived} emails from {len(senders)} senders"
        
    except Exception as e:
        state.archive_status["error"] = str(e)
        state.archive_status["done"] = True
        state.archive_status["message"] = f"Error: {str(e)}"


def get_archive_status() -> dict:
    """Get archive operation status."""
    return state.archive_status.copy()


# ----- Mark Important Functions -----

def mark_important_background(senders: list[str], important: bool = True):
    """Mark/unmark emails from selected senders as important."""
    state.reset_important()
    state.important_status["total_senders"] = len(senders)
    action = "Marking" if important else "Unmarking"
    state.important_status["message"] = f"{action} as important..."
    
    try:
        service = get_gmail_service()
        if not service:
            state.important_status["error"] = "Not authenticated"
            state.important_status["done"] = True
            return
        
        total_affected = 0
        label_action = "addLabelIds" if important else "removeLabelIds"
        
        for i, sender in enumerate(senders):
            state.important_status["current_sender"] = i + 1
            state.important_status["message"] = f"{action} emails from {sender}..."
            state.important_status["progress"] = int((i / len(senders)) * 100)
            
            # Find all emails from this sender
            query = f"from:{sender}"
            message_ids = []
            page_token = None
            
            while True:
                result = service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=500,
                    pageToken=page_token
                ).execute()
                
                messages = result.get('messages', [])
                message_ids.extend([m['id'] for m in messages])
                
                page_token = result.get('nextPageToken')
                if not page_token:
                    break
            
            if not message_ids:
                continue
            
            # Mark in batches
            for j in range(0, len(message_ids), 100):
                batch_ids = message_ids[j:j+100]
                service.users().messages().batchModify(
                    userId='me',
                    body={
                        'ids': batch_ids,
                        label_action: ['IMPORTANT']
                    }
                ).execute()
                total_affected += len(batch_ids)
                
                if j > 0 and j % 500 == 0:
                    import time
                    time.sleep(0.5)
        
        state.important_status["progress"] = 100
        state.important_status["done"] = True
        state.important_status["affected_count"] = total_affected
        action_done = "marked as important" if important else "unmarked as important"
        state.important_status["message"] = f"{total_affected} emails {action_done}"
        
    except Exception as e:
        state.important_status["error"] = str(e)
        state.important_status["done"] = True
        state.important_status["message"] = f"Error: {str(e)}"


def get_important_status() -> dict:
    """Get mark important operation status."""
    return state.important_status.copy()
