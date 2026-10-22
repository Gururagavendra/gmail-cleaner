"""
Tests for Gmail delete operations.
"""

from app.core import state
from app.services.gmail import delete as delete_service


class FakeRequest:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class RecordingMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.list_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        response = self.responses.pop(0) if self.responses else {"messages": []}
        return FakeRequest(response)


class RecordingUsers:
    def __init__(self, messages):
        self._messages = messages

    def messages(self):
        return self._messages


class RecordingService:
    def __init__(self, responses):
        self.messages_api = RecordingMessages(responses)
        self.users_api = RecordingUsers(self.messages_api)

    def users(self):
        return self.users_api


class BatchRetryMessages:
    def __init__(self):
        self.list_calls = []
        self.get_calls = []
        self.responses = {
            "ok": {
                "id": "ok",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Pleo <no-reply@info.pleo.io>"},
                        {"name": "Subject", "value": "First"},
                    ]
                },
            },
            "retry": {
                "id": "retry",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Pleo <no-reply@info.pleo.io>"},
                        {"name": "Subject", "value": "Second"},
                    ]
                },
            },
        }

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return FakeRequest({"messages": [{"id": "ok"}, {"id": "retry"}]})

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return FakeRequest(self.responses[kwargs["id"]])


class BatchRetryBatch:
    def __init__(self, callback, messages):
        self.callback = callback
        self.messages = messages
        self.requests = []

    def add(self, request, request_id=None):
        self.requests.append((request, request_id))

    def execute(self):
        for request, request_id in self.requests:
            if request_id == "retry":
                self.callback(request_id, None, Exception("rate limit"))
            else:
                self.callback(request_id, self.messages.responses[request_id], None)


class BatchRetryService:
    def __init__(self):
        self.messages_api = BatchRetryMessages()
        self.users_api = RecordingUsers(self.messages_api)

    def users(self):
        return self.users_api

    def new_batch_http_request(self, callback):
        return BatchRetryBatch(callback, self.messages_api)


def test_delete_scan_lists_inbox_only(monkeypatch):
    service = RecordingService([{"messages": []}])
    monkeypatch.setattr(delete_service, "get_gmail_service", lambda: (service, None))

    delete_service.scan_senders_for_delete(limit=1000)

    assert service.messages_api.list_calls == [
        {
            "userId": "me",
            "maxResults": 500,
            "q": "in:inbox",
            "labelIds": ["INBOX"],
        }
    ]
    assert state.delete_scan_status["done"] is True


def test_delete_scan_combines_filters_with_inbox(monkeypatch):
    service = RecordingService([{"messages": []}])
    monkeypatch.setattr(delete_service, "get_gmail_service", lambda: (service, None))

    delete_service.scan_senders_for_delete(
        limit=1000, filters={"sender": "no-reply@info.pleo.io"}
    )

    assert service.messages_api.list_calls[0]["q"] == (
        "in:inbox from:no-reply@info.pleo.io"
    )
    assert service.messages_api.list_calls[0]["labelIds"] == ["INBOX"]


def test_delete_scan_can_include_all_mail(monkeypatch):
    service = RecordingService([{"messages": []}])
    monkeypatch.setattr(delete_service, "get_gmail_service", lambda: (service, None))

    delete_service.scan_senders_for_delete(
        limit=1000,
        filters={"sender": "no-reply@info.pleo.io", "mail_scope": "all"},
    )

    assert service.messages_api.list_calls == [
        {
            "userId": "me",
            "maxResults": 500,
            "q": "from:no-reply@info.pleo.io",
        }
    ]


def test_delete_by_sender_searches_inbox_only(monkeypatch):
    service = RecordingService([{"messages": []}])
    monkeypatch.setattr(delete_service, "get_gmail_service", lambda: (service, None))

    result = delete_service.delete_emails_by_sender("no-reply@info.pleo.io")

    assert result["success"] is True
    assert service.messages_api.list_calls == [
        {
            "userId": "me",
            "q": "in:inbox from:no-reply@info.pleo.io",
            "maxResults": 500,
            "labelIds": ["INBOX"],
        }
    ]


def test_delete_by_sender_can_include_all_mail(monkeypatch):
    service = RecordingService([{"messages": []}])
    monkeypatch.setattr(delete_service, "get_gmail_service", lambda: (service, None))

    result = delete_service.delete_emails_by_sender(
        "no-reply@info.pleo.io", mail_scope="all"
    )

    assert result["success"] is True
    assert service.messages_api.list_calls == [
        {
            "userId": "me",
            "q": "from:no-reply@info.pleo.io",
            "maxResults": 500,
        }
    ]


def test_bulk_delete_collects_inbox_only(monkeypatch):
    service = RecordingService([{"messages": []}])
    monkeypatch.setattr(delete_service, "get_gmail_service", lambda: (service, None))

    delete_service.delete_emails_bulk_background(["no-reply@info.pleo.io"])

    assert service.messages_api.list_calls == [
        {
            "userId": "me",
            "q": "in:inbox from:no-reply@info.pleo.io",
            "maxResults": 500,
            "labelIds": ["INBOX"],
        }
    ]
    assert state.delete_bulk_status["done"] is True


def test_delete_scan_retries_failed_batch_metadata_fetch(monkeypatch):
    service = BatchRetryService()
    monkeypatch.setattr(delete_service, "get_gmail_service", lambda: (service, None))

    delete_service.scan_senders_for_delete(limit=1000)

    results = delete_service.get_delete_scan_results()
    assert results[0]["email"] == "no-reply@info.pleo.io"
    assert results[0]["count"] == 2
    assert results[0]["message_ids"] == ["ok", "retry"]
    assert service.messages_api.get_calls[-1]["id"] == "retry"
