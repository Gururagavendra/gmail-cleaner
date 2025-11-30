"""
Gmail Service
-------------
Core Gmail operations: scanning, unsubscribing, marking read, deleting.
"""

import re
import time
import urllib.request
import ssl
from collections import defaultdict
from typing import Optional, Union, Any

from app.core import state
from app.services.auth import get_gmail_service


# ----- Filters -----

def build_gmail_query(filters: Optional[Union[dict, Any]] = None) -> str:
    """Build Gmail search query from filter parameters.
    
    Args:
        filters: dict with keys:
            - older_than: '7d', '30d', '90d', '180d', '365d' or empty
            - larger_than: '1M', '5M', '10M', '25M' or empty
            - category: 'promotions', 'social', 'updates', 'forums', 'primary' or empty
    
    Returns:
        Gmail query string, empty string if no filters
    """
    if not filters:
        return ""
    
    # Handle both dict and Pydantic model
    if hasattr(filters, 'model_dump'):
        filters = filters.model_dump(exclude_none=True)
    
    query_parts = []
    
    if older_than := filters.get('older_than', ''):
        query_parts.append(f'older_than:{older_than}')
    
    if larger_than := filters.get('larger_than', ''):
        query_parts.append(f'larger:{larger_than}')
    
    if category := filters.get('category', ''):
        query_parts.append(f'category:{category}')
    
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
        unsubscribe_data = defaultdict(lambda: {"link": None, "count": 0, "subjects": [], "type": None})
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
                
                unsubscribe_data[domain]["link"] = unsub_link
                unsubscribe_data[domain]["count"] += 1
                unsubscribe_data[domain]["type"] = unsub_type
                unsubscribe_data[domain]["sender"] = sender_name
                unsubscribe_data[domain]["email"] = sender_email
                if len(unsubscribe_data[domain]["subjects"]) < 3:
                    unsubscribe_data[domain]["subjects"].append(subject)
        
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
                        metadataHeaders=['From', 'Subject', 'List-Unsubscribe', 'List-Unsubscribe-Post']
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
              "type": v["type"], "sender": v.get("sender", ""), "email": v.get("email", "")} 
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
        # Create SSL context that doesn't verify (some unsubscribe servers have bad certs)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
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
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                if response.status in [200, 201, 202, 204]:
                    return {"success": True, "message": "Unsubscribed successfully", "domain": domain}
        except Exception:
            pass
        
        # Fallback to GET
        req = urllib.request.Request(
            link,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; GmailUnsubscribe/1.0)'}
        )
        
        with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
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
        sender_counts = defaultdict(lambda: {"count": 0, "sender": "", "email": "", "subjects": []})
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
            if sender_email:
                sender_counts[sender_email]["count"] += 1
                sender_counts[sender_email]["sender"] = sender_name
                sender_counts[sender_email]["email"] = sender_email
                if len(sender_counts[sender_email]["subjects"]) < 3:
                    sender_counts[sender_email]["subjects"].append(subject)
        
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
                        metadataHeaders=['From', 'Subject']
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
        return {"success": False, "deleted": 0, "message": "No sender specified"}
    
    service, error = get_gmail_service()
    if error:
        return {"success": False, "deleted": 0, "message": error}
    
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
            return {"success": True, "deleted": 0, "message": "No emails found"}
        
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
        
        return {"success": True, "deleted": deleted, "message": f"Moved {deleted} emails to trash"}
        
    except Exception as e:
        return {"success": False, "deleted": 0, "message": str(e)}


def delete_emails_bulk(senders: list[str]) -> dict:
    """Delete emails from multiple senders."""
    if not senders:
        return {"success": False, "deleted": 0, "message": "No senders specified"}
    
    total_deleted = 0
    errors = []
    
    for sender in senders:
        result = delete_emails_by_sender(sender)
        if result["success"]:
            total_deleted += result["deleted"]
        else:
            errors.append(f"{sender}: {result['message']}")
    
    if errors:
        return {
            "success": len(errors) < len(senders),
            "deleted": total_deleted,
            "message": f"Deleted {total_deleted} emails. Errors: {'; '.join(errors[:3])}"
        }
    
    if total_deleted == 0:
        return {"success": False, "deleted": 0, "message": "No emails found to delete"}
    return {"success": True, "deleted": total_deleted, "message": f"Deleted {total_deleted} emails"}
