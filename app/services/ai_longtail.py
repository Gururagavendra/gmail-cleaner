"""
AI Long-tail Email Classification
---------------------------------
Proof-of-concept helpers for classifying one inbox email with an
OpenAI-compatible chat completions API.
"""

import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core import settings, state
from app.services.auth import get_gmail_service
from app.services.gmail.helpers import build_gmail_query, get_sender_info, get_subject

logger = logging.getLogger(__name__)


AI_PROVIDERS: dict[str, dict[str, str]] = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4.1-mini",
    },
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    "mistral": {
        "name": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-small-latest",
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
    },
    "together": {
        "name": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    },
}

CLASSIFICATION_CATEGORIES = [
    "marketing",
    "newsletter",
    "notification",
    "receipt",
    "order",
    "account",
    "security",
    "legal",
    "finance",
    "tax",
    "human_personal",
    "work",
    "customer",
    "supplier",
    "system",
    "unknown",
]

RECOMMENDED_ACTIONS = ["delete", "archive", "keep_in_inbox", "manual_review"]
CLASSIFIER_VERSION = 2

UNSOLICITED_OUTREACH_PATTERNS = [
    r"\bcomplimentary\b",
    r"\bfree\b.*\b(audit|scan|assessment|consultation)\b",
    r"\b(ux|seo|website|performance)\s+(audit|scan|assessment)\b",
    r"\bquick\s+(15|20|30)[-\s]?minute\s+(chat|call)\b",
    r"\b(brief|quick)\s+(chat|call)\b",
    r"\bwould you be interested\b",
    r"\bworth having\b.*\bcall\b",
    r"\bjust\s+(circling|checking)\s+back\b",
    r"\breach(?:ing)? out\b",
    r"\bno pressure\b",
    r"\blearn more\b",
    r"\bshow you\b",
    r"\bbook\s+(a\s+)?(call|demo|meeting)\b",
    r"\bupgrade your circle\b",
    r"\bfounders club\b",
    r"\bjoin(?:ing)?\b.*\bclub\b",
    r"\bmake sure not to follow up\b",
    r"\bdoesn.t sound like something\b.*\binterest\b",
    r"\bghost me\b",
]


@dataclass
class AIConfig:
    provider: str
    api_key: str
    model: str
    base_url: str


def get_ai_providers() -> list[dict[str, str]]:
    """Return provider options safe to show in the UI."""
    return [{"id": provider_id, **provider} for provider_id, provider in AI_PROVIDERS.items()]


def get_ai_config_status() -> dict[str, Any]:
    """Return AI configuration metadata without exposing the API token."""
    config = load_ai_config()
    if not config:
        return {
            "configured": False,
            "providers": get_ai_providers(),
            "default_provider": "openai",
        }

    provider_name = AI_PROVIDERS.get(config.provider, {}).get("name", config.provider)
    return {
        "configured": True,
        "provider": config.provider,
        "provider_name": provider_name,
        "model": config.model,
        "base_url": config.base_url,
        "providers": get_ai_providers(),
        "default_provider": config.provider,
    }


def save_ai_config(provider: str, api_key: str, model: str, base_url: str) -> dict:
    """Persist AI credentials to the local ai_token.json file."""
    provider = provider.strip().lower()
    api_key = api_key.strip()
    model = model.strip()
    base_url = normalize_base_url(base_url)

    if provider not in AI_PROVIDERS:
        raise ValueError("Unsupported AI provider")
    if not api_key:
        raise ValueError("API token is required")
    if not model:
        raise ValueError("Model is required")

    token_path = Path(settings.ai_token_file)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(
        json.dumps(
            {
                "provider": provider,
                "api_key": api_key,
                "model": model,
                "base_url": base_url,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    try:
        token_path.chmod(0o600)
    except OSError:
        pass

    return get_ai_config_status()


def load_ai_config() -> AIConfig | None:
    """Load local AI configuration, returning None when not configured."""
    token_path = Path(settings.ai_token_file)
    if not token_path.exists():
        return None

    try:
        raw = json.loads(token_path.read_text(encoding="utf-8"))
        provider = str(raw.get("provider", "")).strip().lower()
        api_key = str(raw.get("api_key", "")).strip()
        model = str(raw.get("model", "")).strip()
        base_url = normalize_base_url(str(raw.get("base_url", "")).strip())
    except (OSError, json.JSONDecodeError, ValueError):
        logger.exception("Failed to load AI config")
        return None

    if provider not in AI_PROVIDERS or not api_key or not model or not base_url:
        return None

    return AIConfig(provider=provider, api_key=api_key, model=model, base_url=base_url)


def normalize_base_url(base_url: str) -> str:
    """Validate and normalize an OpenAI-compatible base URL."""
    base_url = base_url.strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Base URL must be a valid HTTPS URL")
    return base_url


def classify_one_long_tail_email(
    filters: dict | None = None, sender: str | None = None
) -> dict:
    """Fetch one inbox email and classify it through the configured AI provider."""
    config = load_ai_config()
    if not config:
        return {
            "success": False,
            "needs_ai_config": True,
            "message": "Add an AI provider and API token before classifying emails.",
        }

    service, error = get_gmail_service()
    if error:
        return {"success": False, "error": error}

    try:
        email_data = fetch_one_inbox_email(service, filters, sender)
        if not email_data:
            message = "No inbox emails found for the current filters."
            if sender:
                message = f"No inbox emails found from {sender}."
            return {
                "success": True,
                "message": message,
                "email": None,
                "classification": None,
            }

        classification = classify_email_with_ai(config, email_data)
        return {
            "success": True,
            "message": "Classified one inbox email.",
            "email": email_data,
            "classification": classification,
        }
    except Exception as e:
        logger.exception("Long-tail classification failed")
        return {"success": False, "error": str(e)}


def scan_long_tail_candidates(
    limit: int = 1000, sender_threshold: int = 2, filters: dict | None = None
) -> None:
    """Scan inbox emails and keep only emails from low-volume senders."""
    if limit <= 0:
        state.reset_long_tail_scan()
        state.long_tail_scan_status["error"] = "Limit must be greater than 0"
        state.long_tail_scan_status["done"] = True
        return

    if sender_threshold <= 0:
        state.reset_long_tail_scan()
        state.long_tail_scan_status["error"] = "Sender threshold must be greater than 0"
        state.long_tail_scan_status["done"] = True
        return

    state.reset_long_tail_scan()
    state.long_tail_scan_status["message"] = "Connecting to Gmail..."

    service, error = get_gmail_service()
    if error:
        state.long_tail_scan_status["error"] = error
        state.long_tail_scan_status["done"] = True
        return

    try:
        query = "in:inbox"
        filter_query = build_gmail_query(filters)
        if filter_query:
            query = f"{query} {filter_query}"

        state.long_tail_scan_status["message"] = "Fetching inbox emails..."
        messages = list_message_refs(service, limit, query)

        if not messages:
            state.long_tail_scan_results = {
                "summary": {
                    "scanned_emails": 0,
                    "total_senders": 0,
                    "candidate_senders": 0,
                    "candidate_emails": 0,
                    "sender_threshold": sender_threshold,
                    "search_query": query,
                },
                "senders": [],
                "emails": [],
            }
            state.long_tail_scan_status["message"] = "No inbox emails found"
            state.long_tail_scan_status["done"] = True
            return

        sender_groups = fetch_grouped_email_metadata(service, messages, query)
        candidate_senders = [
            sender
            for sender in sender_groups.values()
            if sender["count"] <= sender_threshold
        ]
        candidate_senders.sort(key=lambda item: (item["count"], item["email"]))

        candidate_emails = []
        for sender in candidate_senders:
            candidate_emails.extend(sender["emails"])

        state.long_tail_scan_results = {
            "summary": {
                "scanned_emails": len(messages),
                "total_senders": len(sender_groups),
                "candidate_senders": len(candidate_senders),
                "candidate_emails": len(candidate_emails),
                "sender_threshold": sender_threshold,
                "search_query": query,
            },
            "senders": [
                {
                    "sender": sender["sender"],
                    "email": sender["email"],
                    "count": sender["count"],
                    "subjects": sender["subjects"],
                    "first_date": sender["first_date"],
                    "last_date": sender["last_date"],
                }
                for sender in candidate_senders
            ],
            "emails": candidate_emails,
        }
        state.long_tail_scan_status["progress"] = 100
        state.long_tail_scan_status["message"] = (
            f"Found {len(candidate_emails)} emails from "
            f"{len(candidate_senders)} long-tail senders"
        )
        state.long_tail_scan_status["done"] = True
    except Exception as e:
        logger.exception("Long-tail scan failed")
        state.long_tail_scan_status["error"] = str(e)
        state.long_tail_scan_status["done"] = True


def get_long_tail_scan_status() -> dict:
    """Get current long-tail scan status."""
    return state.long_tail_scan_status.copy()


def get_long_tail_scan_results() -> dict:
    """Get long-tail scan results."""
    return {
        "summary": dict(state.long_tail_scan_results.get("summary", {})),
        "senders": list(state.long_tail_scan_results.get("senders", [])),
        "emails": list(state.long_tail_scan_results.get("emails", [])),
    }


def classify_long_tail_candidates_background(
    max_emails: int = 25, use_cache: bool = True
) -> None:
    """Classify scanned long-tail candidate emails with AI."""
    state.reset_long_tail_classify()

    config = load_ai_config()
    if not config:
        state.long_tail_classify_status["error"] = (
            "Add an AI provider and API token before classifying emails."
        )
        state.long_tail_classify_status["done"] = True
        return

    emails = list(state.long_tail_scan_results.get("emails", []))[:max_emails]
    if not emails:
        state.long_tail_classify_status["message"] = "No long-tail emails to classify"
        state.long_tail_classify_status["done"] = True
        return

    cache = load_classification_cache() if use_cache else {}
    total = len(emails)
    state.long_tail_classify_status["total_emails"] = total
    state.long_tail_classify_status["message"] = f"Classifying {total} emails..."

    results = []
    for index, email_data in enumerate(emails, start=1):
        if state.long_tail_cancel_requested:
            state.long_tail_classify_status["message"] = (
                f"Cancelled after {len(results)}/{total} emails"
            )
            state.long_tail_classify_status["done"] = True
            return

        message_id = email_data.get("id")
        try:
            state.long_tail_classify_status["message"] = (
                f"Classifying {index}/{total}: {email_data.get('from_email', '')}"
            )
            cached = get_valid_cached_classification(cache, message_id)
            if cached:
                classification = cached["classification"]
                state.long_tail_classify_status["cached_count"] += 1
            else:
                classification = classify_email_with_ai(config, email_data)
                if message_id:
                    cache[message_id] = {
                        "email": email_data,
                        "classification": classification,
                        "provider": config.provider,
                        "model": config.model,
                        "classifier_version": CLASSIFIER_VERSION,
                        "created_at": int(time.time()),
                    }
                    save_classification_cache(cache)

            result = {
                "email": email_data,
                "classification": classification,
                "cached": bool(cached),
                "error": None,
            }
            results.append(result)
            state.long_tail_classify_results = results.copy()
            state.long_tail_classify_status["classified_count"] = index
            state.long_tail_classify_status["progress"] = int(index / total * 100)
            if not cached:
                # Keep provider calls gentle during early debugging.
                time.sleep(0.15)
        except Exception as e:
            logger.exception("Long-tail classification failed for one email")
            state.long_tail_classify_status["error_count"] += 1
            results.append(
                {
                    "email": email_data,
                    "classification": None,
                    "cached": False,
                    "error": str(e),
                }
            )
            state.long_tail_classify_results = results.copy()
            state.long_tail_classify_status["classified_count"] = index
            state.long_tail_classify_status["progress"] = int(index / total * 100)

    state.long_tail_classify_status["progress"] = 100
    state.long_tail_classify_status["message"] = (
        f"Processed {total} emails "
        f"({state.long_tail_classify_status['cached_count']} cached, "
        f"{state.long_tail_classify_status['error_count']} errors)"
    )
    state.long_tail_classify_status["done"] = True


def cancel_long_tail_classification() -> dict:
    """Request cancellation of the active long-tail classification job."""
    state.long_tail_cancel_requested = True
    return {"status": "cancelling"}


def get_long_tail_classify_status() -> dict:
    """Get long-tail AI classification status."""
    return state.long_tail_classify_status.copy()


def get_long_tail_classify_results() -> list:
    """Get long-tail AI classification results."""
    return state.long_tail_classify_results.copy()


def apply_long_tail_actions_background(actions: list[dict]) -> None:
    """Apply reviewed delete/archive actions to specific Gmail message IDs."""
    state.reset_long_tail_apply()

    if not actions:
        state.long_tail_apply_status["error"] = "No actions selected"
        state.long_tail_apply_status["done"] = True
        return

    service, error = get_gmail_service()
    if error:
        state.long_tail_apply_status["error"] = error
        state.long_tail_apply_status["done"] = True
        return

    delete_ids = dedupe_ids(
        action["message_id"] for action in actions if action.get("action") == "delete"
    )
    archive_ids = dedupe_ids(
        action["message_id"] for action in actions if action.get("action") == "archive"
    )
    total = len(delete_ids) + len(archive_ids)
    state.long_tail_apply_status["total_emails"] = total

    if total == 0:
        state.long_tail_apply_status["error"] = "No delete or archive actions selected"
        state.long_tail_apply_status["done"] = True
        return

    processed = 0
    errors = []

    try:
        if delete_ids:
            state.long_tail_apply_status["message"] = (
                f"Moving {len(delete_ids)} emails to trash..."
            )
            trashed = batch_modify_message_ids(
                service,
                delete_ids,
                add_label_ids=["TRASH"],
                progress_callback=lambda count: update_long_tail_apply_progress(
                    processed + count, total
                ),
            )
            processed += trashed
            state.long_tail_apply_status["trashed_count"] = trashed

        if archive_ids:
            state.long_tail_apply_status["message"] = (
                f"Archiving {len(archive_ids)} emails..."
            )
            archived = batch_modify_message_ids(
                service,
                archive_ids,
                remove_label_ids=["INBOX"],
                progress_callback=lambda count: update_long_tail_apply_progress(
                    processed + count, total
                ),
            )
            processed += archived
            state.long_tail_apply_status["archived_count"] = archived
    except Exception as e:
        logger.exception("Long-tail apply actions failed")
        errors.append(str(e))

    state.long_tail_apply_status["progress"] = 100
    state.long_tail_apply_status["done"] = True

    if errors:
        state.long_tail_apply_status["error"] = "; ".join(errors[:3])
        state.long_tail_apply_status["message"] = (
            f"Applied {processed}/{total} actions with errors"
        )
    else:
        state.long_tail_apply_status["message"] = (
            f"Moved {state.long_tail_apply_status['trashed_count']} to trash and "
            f"archived {state.long_tail_apply_status['archived_count']}"
        )


def get_long_tail_apply_status() -> dict:
    """Get long-tail apply action status."""
    return state.long_tail_apply_status.copy()


def dedupe_ids(message_ids) -> list[str]:
    """Dedupe message IDs while preserving order."""
    seen = set()
    deduped = []
    for message_id in message_ids:
        if message_id and message_id not in seen:
            deduped.append(message_id)
            seen.add(message_id)
    return deduped


def batch_modify_message_ids(
    service,
    message_ids: list[str],
    *,
    add_label_ids: list[str] | None = None,
    remove_label_ids: list[str] | None = None,
    progress_callback=None,
) -> int:
    """Apply a Gmail batchModify operation in efficient chunks."""
    affected = 0
    batch_size = 1000

    for i in range(0, len(message_ids), batch_size):
        batch = message_ids[i : i + batch_size]
        body = {"ids": batch}
        if add_label_ids:
            body["addLabelIds"] = add_label_ids
        if remove_label_ids:
            body["removeLabelIds"] = remove_label_ids

        service.users().messages().batchModify(userId="me", body=body).execute()
        affected += len(batch)
        if progress_callback:
            progress_callback(affected)

    return affected


def update_long_tail_apply_progress(processed: int, total: int) -> None:
    """Update long-tail apply action progress."""
    state.long_tail_apply_status["progress"] = int(processed / total * 100)
    state.long_tail_apply_status["message"] = f"Applied {processed}/{total} actions..."


def load_classification_cache() -> dict:
    """Load persisted classifications keyed by Gmail message id."""
    cache_path = Path(settings.ai_classification_cache_file)
    if not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to load AI classification cache")
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload.get("classifications", {}) if isinstance(payload.get("classifications"), dict) else {}


def save_classification_cache(classifications: dict) -> None:
    """Persist classifications to local disk."""
    cache_path = Path(settings.ai_classification_cache_file)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": int(time.time()),
                "classifications": classifications,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def get_valid_cached_classification(cache: dict, message_id: str | None) -> dict | None:
    """Return a cached classification only when it matches the active classifier."""
    if not message_id:
        return None
    cached = cache.get(message_id)
    if not cached:
        return None
    if cached.get("classifier_version") != CLASSIFIER_VERSION:
        return None
    return cached


def fetch_one_inbox_email(
    service, filters: dict | None = None, sender: str | None = None
) -> dict | None:
    """Fetch compact metadata for one inbox email."""
    query = "in:inbox"
    filter_query = build_gmail_query(filters)
    if filter_query:
        query = f"{query} {filter_query}"
    if sender:
        query = f"{query} from:{sender.strip()}"

    max_results = 25 if sender else 1
    result = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, q=query)
        .execute()
    )
    messages = result.get("messages", [])
    if not messages:
        return None

    for message_ref in messages:
        message = fetch_message_metadata(service, message_ref["id"])
        email_data = format_email_metadata(message, query)
        if not sender or sender_matches(email_data["from_email"], sender):
            return email_data

    return None


def list_message_refs(service, limit: int, query: str) -> list[dict]:
    """List Gmail message refs up to a limit."""
    message_refs = []
    page_token = None

    while len(message_refs) < limit:
        list_params = {
            "userId": "me",
            "maxResults": min(500, limit - len(message_refs)),
            "q": query,
        }
        if page_token:
            list_params["pageToken"] = page_token

        result = service.users().messages().list(**list_params).execute()
        message_refs.extend(result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return message_refs[:limit]


def fetch_grouped_email_metadata(
    service, message_refs: list[dict], query: str
) -> dict[str, dict]:
    """Fetch message metadata in batches and group by sender."""
    sender_groups: dict[str, dict] = defaultdict(
        lambda: {
            "count": 0,
            "sender": "",
            "email": "",
            "subjects": [],
            "first_date": None,
            "last_date": None,
            "emails": [],
        }
    )
    processed = 0
    total = len(message_refs)
    batch_size = 100

    def process_message(request_id, response, exception) -> None:
        nonlocal processed
        processed += 1

        if exception:
            return

        email_data = format_email_metadata(response, query)
        sender_email = email_data.get("from_email", "")
        if not sender_email:
            return

        sender = sender_groups[sender_email]
        sender["count"] += 1
        sender["sender"] = email_data.get("from_name", sender_email)
        sender["email"] = sender_email
        sender["emails"].append(email_data)
        if len(sender["subjects"]) < 3:
            sender["subjects"].append(email_data.get("subject", ""))

        email_date = email_data.get("date")
        if email_date:
            if sender["first_date"] is None:
                sender["first_date"] = email_date
            sender["last_date"] = email_date

    for i in range(0, len(message_refs), batch_size):
        batch_refs = message_refs[i : i + batch_size]
        batch = service.new_batch_http_request(callback=process_message)

        for msg_ref in batch_refs:
            batch.add(
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg_ref["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                )
            )

        batch.execute()

        state.long_tail_scan_status["progress"] = int(
            (i + len(batch_refs)) / total * 100
        )
        state.long_tail_scan_status["message"] = f"Scanned {processed}/{total} emails"

        if (i // batch_size + 1) % 5 == 0:
            time.sleep(0.3)

    return dict(sender_groups)


def fetch_message_metadata(service, message_id: str) -> dict:
    """Fetch Gmail message metadata by id."""
    return (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        )
        .execute()
    )


def format_email_metadata(message: dict, query: str) -> dict:
    """Format Gmail message metadata for AI classification."""
    headers = message.get("payload", {}).get("headers", [])
    sender_name, sender_email = get_sender_info(headers)
    subject = get_subject(headers)
    email_date = get_header(headers, "Date")
    label_ids = message.get("labelIds", [])

    return {
        "id": message.get("id"),
        "thread_id": message.get("threadId"),
        "from_name": sender_name,
        "from_email": sender_email,
        "subject": subject,
        "date": email_date,
        "date_iso": parse_email_date(email_date),
        "snippet": message.get("snippet", ""),
        "labels": label_ids,
        "has_attachments": has_attachments(message.get("payload", {})),
        "search_query": query,
    }


def sender_matches(actual_sender: str, requested_sender: str) -> bool:
    """Check that a Gmail result really matches the requested sender."""
    actual = actual_sender.strip().lower()
    requested = requested_sender.strip().lower()

    if not actual or not requested:
        return False

    if "@" in requested:
        return actual == requested

    domain = actual.split("@")[-1] if "@" in actual else actual
    return domain == requested or domain.endswith(f".{requested}")


def classify_email_with_ai(config: AIConfig, email_data: dict) -> dict:
    """Classify a compact email payload using chat completions."""
    payload = {
        "model": config.model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You classify Gmail inbox messages for safe clean-up. Be strict. "
                    "Cold outreach, sales prospecting, lead generation, networking clubs, "
                    "webinars, complimentary audits, free scans, demos, agency pitches, "
                    "and follow-up/circling-back sequences are marketing unless the email "
                    "clearly shows an existing active customer/supplier relationship. "
                    "Do not call a message work just because it mentions the user's company, "
                    "B2B, revenue, ecommerce, UX, web development, or business growth. "
                    "Return only JSON with keys: id, category, recommended_action, "
                    "confidence, reason. Confidence must be a number from 0 to 1. "
                    "Use these categories: "
                    f"{', '.join(CLASSIFICATION_CATEGORIES)}. "
                    "Use these actions: delete, archive, keep_in_inbox, manual_review. "
                    "For obvious unsolicited sales/marketing outreach, use category "
                    "marketing, recommended_action delete, confidence at least 0.90. "
                    "Examples of marketing: 'complimentary UX audit', 'quick 20-minute chat', "
                    "'just circling back', 'would you be interested', 'Founders Club', "
                    "'upgrade your circle', and 'if this does not interest you I will not follow up'. "
                    "Never recommend delete for receipts, orders, account, security, "
                    "legal, finance, tax, human, work, customer, supplier, or unknown mail."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(email_data, ensure_ascii=True),
            },
        ],
    }

    request = Request(
        f"{config.base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as err:
        details = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AI provider returned HTTP {err.code}: {details}") from err
    except URLError as err:
        raise RuntimeError(f"Could not reach AI provider: {err.reason}") from err

    content = (
        response_payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    classification = parse_classification(content)
    classification = apply_classification_overrides(email_data, classification)
    classification["id"] = str(classification.get("id") or email_data["id"])
    classification["token_usage"] = normalize_token_usage(
        response_payload.get("usage", {})
    )
    classification["raw_model_output"] = content
    return classification


def parse_classification(content: str) -> dict:
    """Parse and sanitize model JSON output."""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise ValueError("AI response did not contain JSON") from None
        parsed = json.loads(match.group(0))

    category = str(parsed.get("category", "unknown")).strip()
    if category not in CLASSIFICATION_CATEGORIES:
        category = "unknown"

    action = str(parsed.get("recommended_action", "manual_review")).strip()
    if action not in RECOMMENDED_ACTIONS:
        action = "manual_review"

    confidence = normalize_confidence(
        parsed.get("confidence", parsed.get("confidence_score", 0))
    )

    return {
        "id": str(parsed.get("id", "")),
        "category": category,
        "recommended_action": action,
        "confidence": confidence,
        "reason": str(parsed.get("reason", "")).strip(),
    }


def apply_classification_overrides(email_data: dict, classification: dict) -> dict:
    """Apply deterministic cleanup rules for cases LLMs commonly misclassify."""
    text = " ".join(
        str(value or "")
        for value in [
            email_data.get("from_name"),
            email_data.get("from_email"),
            email_data.get("subject"),
            email_data.get("snippet"),
            classification.get("reason"),
        ]
    ).lower()

    matched = [
        pattern
        for pattern in UNSOLICITED_OUTREACH_PATTERNS
        if re.search(pattern, text, re.IGNORECASE)
    ]

    if len(matched) >= 2:
        return {
            **classification,
            "category": "marketing",
            "recommended_action": "delete",
            "confidence": max_confidence(classification.get("confidence"), 0.92),
            "reason": (
                "Unsolicited sales/marketing outreach detected: "
                "cold pitch or follow-up asking for a chat, audit, demo, club, or service review."
            ),
            "override": "unsolicited_outreach",
        }

    return classification


def max_confidence(current: float | None, minimum: float) -> float:
    """Return at least the minimum confidence."""
    if current is None:
        return minimum
    return max(current, minimum)


def normalize_confidence(value) -> float | None:
    """Normalize model confidence output into the 0-1 range."""
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        if value.endswith("%"):
            value = value[:-1].strip()
            try:
                return max(0, min(float(value) / 100, 1))
            except ValueError:
                return None

    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None

    if confidence > 1:
        confidence = confidence / 100

    return max(0, min(confidence, 1))


def normalize_token_usage(usage: dict) -> dict:
    """Normalize OpenAI-compatible token usage fields for display."""
    if not isinstance(usage, dict):
        usage = {}

    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    total_tokens = usage.get("total_tokens")

    return {
        "input_tokens": coerce_token_count(input_tokens),
        "output_tokens": coerce_token_count(output_tokens),
        "total_tokens": coerce_token_count(total_tokens),
        "raw": usage,
    }


def coerce_token_count(value) -> int | None:
    """Convert token counts to integers when present."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_header(headers: list[dict], name: str) -> str | None:
    """Return a header value by case-insensitive name."""
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value")
    return None


def parse_email_date(date_value: str | None) -> str | None:
    """Parse an email header date into ISO format when possible."""
    if not date_value:
        return None
    try:
        return parsedate_to_datetime(date_value).isoformat()
    except (TypeError, ValueError):
        return None


def has_attachments(payload: dict) -> bool:
    """Detect whether a Gmail message payload includes attachments."""
    filename = payload.get("filename")
    body = payload.get("body", {})
    if filename and body.get("attachmentId"):
        return True

    return any(has_attachments(part) for part in payload.get("parts", []))
