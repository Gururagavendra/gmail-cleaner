"""
Tests for AI long-tail classification helpers.
"""

import json

from app.services.ai_longtail import (
    CLASSIFIER_VERSION,
    apply_classification_overrides,
    batch_modify_message_ids,
    dedupe_ids,
    fetch_one_inbox_email,
    load_classification_cache,
    normalize_confidence,
    normalize_token_usage,
    parse_classification,
    save_classification_cache,
    sender_matches,
)


class TestAIClassificationParsing:
    """Tests for model response parsing."""

    def test_parse_confidence_percentage_string(self):
        """Percentage confidence strings should be normalized to 0-1."""
        result = parse_classification(
            json.dumps(
                {
                    "id": "msg-1",
                    "category": "newsletter",
                    "recommended_action": "delete",
                    "confidence": "95%",
                    "reason": "Newsletter style content",
                }
            )
        )

        assert result["confidence"] == 0.95

    def test_parse_confidence_score_alias(self):
        """Common confidence_score alias should be accepted."""
        result = parse_classification(
            json.dumps(
                {
                    "id": "msg-1",
                    "category": "notification",
                    "recommended_action": "archive",
                    "confidence_score": 82,
                    "reason": "Automated notification",
                }
            )
        )

        assert result["confidence"] == 0.82

    def test_normalize_confidence_bounds_values(self):
        """Confidence values should stay within 0-1."""
        assert normalize_confidence(-10) == 0
        assert normalize_confidence(150) == 1
        assert normalize_confidence("bad") is None

    def test_unsolicited_ux_audit_is_marketing_delete(self):
        """Cold UX audit outreach should not be classified as work."""
        email = {
            "from_name": "Alex Saxon",
            "from_email": "alex.s@trydigitalgroup.com",
            "subject": "Complimentary UX audit for Shopblocks",
            "snippet": (
                "Just circling back on my earlier note. I ran a quick scan at "
                "Shopblocks's website and would be happy to show a complimentary "
                "UX audit. Would you be interested in a quick 20-minute chat?"
            ),
        }
        result = apply_classification_overrides(
            email,
            {
                "category": "work",
                "recommended_action": "keep_in_inbox",
                "confidence": 0.81,
                "reason": "Mentions Shopblocks and UX work",
            },
        )

        assert result["category"] == "marketing"
        assert result["recommended_action"] == "delete"
        assert result["confidence"] >= 0.92

    def test_unsolicited_founders_club_is_marketing_delete(self):
        """Cold networking club outreach should not be classified as work."""
        email = {
            "from_name": "Aaron Spivak",
            "from_email": "aaronspivak@entreprenuerapp.com",
            "subject": "Re: Congratulations to Kevin and ShopBlocks",
            "snippet": (
                "Is it worth having a 15-minute call to learn more and see if "
                "joining would be a good move? You'd be a great fit for The "
                "Founders Club. If this doesn't interest you I'll make sure not "
                "to follow up."
            ),
        }
        result = apply_classification_overrides(
            email,
            {
                "category": "work",
                "recommended_action": "keep_in_inbox",
                "confidence": 0.77,
                "reason": "Business networking opportunity",
            },
        )

        assert result["category"] == "marketing"
        assert result["recommended_action"] == "delete"
        assert result["confidence"] >= 0.92


class TestAITokenUsage:
    """Tests for token usage normalization."""

    def test_normalize_openai_usage(self):
        """OpenAI-compatible usage fields should map to display fields."""
        usage = normalize_token_usage(
            {
                "prompt_tokens": 120,
                "completion_tokens": 34,
                "total_tokens": 154,
            }
        )

        assert usage["input_tokens"] == 120
        assert usage["output_tokens"] == 34
        assert usage["total_tokens"] == 154

    def test_normalize_usage_aliases(self):
        """Provider aliases for token usage should be accepted."""
        usage = normalize_token_usage(
            {
                "input_tokens": "100",
                "output_tokens": "25",
            }
        )

        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 25
        assert usage["total_tokens"] is None


class TestLongTailEmailFetch:
    """Tests for Gmail query construction."""

    def test_fetch_one_inbox_email_filters_by_sender(self):
        """Sender input should be added to the Gmail query."""

        class ExecuteResponse:
            def __init__(self, payload):
                self.payload = payload

            def execute(self):
                return self.payload

        class Messages:
            def __init__(self):
                self.list_query = None
                self.get_ids = []

            def list(self, **kwargs):
                self.list_query = kwargs["q"]
                return ExecuteResponse({"messages": [{"id": "msg-1"}]})

            def get(self, **kwargs):
                self.get_ids.append(kwargs["id"])
                return ExecuteResponse(
                    {
                        "id": kwargs["id"],
                        "threadId": "thread-1",
                        "labelIds": ["INBOX"],
                        "snippet": "Preview",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "News <news@example.com>"},
                                {"name": "Subject", "value": "Latest update"},
                            ]
                        },
                    }
                )

        class Users:
            def __init__(self):
                self.messages_api = Messages()

            def messages(self):
                return self.messages_api

        class Service:
            def __init__(self):
                self.users_api = Users()

            def users(self):
                return self.users_api

        service = Service()
        result = fetch_one_inbox_email(service, sender="news@example.com")

        assert result["id"] == "msg-1"
        assert service.users_api.messages_api.list_query == (
            "in:inbox from:news@example.com"
        )

    def test_fetch_one_inbox_email_skips_non_matching_sender(self):
        """A requested sender must match the actual From header before classify."""

        class ExecuteResponse:
            def __init__(self, payload):
                self.payload = payload

            def execute(self):
                return self.payload

        class Messages:
            def __init__(self):
                self.get_ids = []

            def list(self, **kwargs):
                return ExecuteResponse(
                    {"messages": [{"id": "wrong"}, {"id": "right"}]}
                )

            def get(self, **kwargs):
                self.get_ids.append(kwargs["id"])
                sender = (
                    "Other <other@example.com>"
                    if kwargs["id"] == "wrong"
                    else "News <news@example.com>"
                )
                return ExecuteResponse(
                    {
                        "id": kwargs["id"],
                        "threadId": "thread-1",
                        "labelIds": ["INBOX"],
                        "snippet": "Preview",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": sender},
                                {"name": "Subject", "value": "Latest update"},
                            ]
                        },
                    }
                )

        class Users:
            def __init__(self):
                self.messages_api = Messages()

            def messages(self):
                return self.messages_api

        class Service:
            def __init__(self):
                self.users_api = Users()

            def users(self):
                return self.users_api

        service = Service()
        result = fetch_one_inbox_email(service, sender="news@example.com")

        assert result["id"] == "right"
        assert service.users_api.messages_api.get_ids == ["wrong", "right"]

    def test_sender_matches_email_and_domain(self):
        """Sender matching supports exact email or domain input."""
        assert sender_matches("news@example.com", "news@example.com")
        assert sender_matches("news@mail.example.com", "example.com")
        assert not sender_matches("other@example.com", "news@example.com")


class TestClassificationCache:
    """Tests for persisted AI classification cache."""

    def test_save_and_load_classification_cache(self, monkeypatch, tmp_path):
        """Classification cache should round-trip through disk."""
        cache_file = tmp_path / "ai_classifications.json"
        monkeypatch.setattr(
            "app.services.ai_longtail.settings.ai_classification_cache_file",
            str(cache_file),
        )

        save_classification_cache(
            {
                "msg-1": {
                    "classification": {"category": "newsletter"},
                    "email": {"id": "msg-1"},
                }
            }
        )

        loaded = load_classification_cache()
        assert loaded["msg-1"]["classification"]["category"] == "newsletter"

    def test_classifier_version_constant_is_current(self):
        """The classifier version should invalidate older poor classifications."""
        assert CLASSIFIER_VERSION == 2


class TestApplyActions:
    """Tests for efficient Gmail action application helpers."""

    def test_dedupe_ids_preserves_order(self):
        """Duplicate IDs should be removed before batch operations."""
        assert dedupe_ids(["a", "b", "a", "", "c"]) == ["a", "b", "c"]

    def test_batch_modify_message_ids_uses_batch_modify(self):
        """Gmail action helper should use batchModify with label changes."""

        class ExecuteResponse:
            def execute(self):
                return {}

        class Messages:
            def __init__(self):
                self.calls = []

            def batchModify(self, **kwargs):
                self.calls.append(kwargs)
                return ExecuteResponse()

        class Users:
            def __init__(self):
                self.messages_api = Messages()

            def messages(self):
                return self.messages_api

        class Service:
            def __init__(self):
                self.users_api = Users()

            def users(self):
                return self.users_api

        service = Service()
        affected = batch_modify_message_ids(
            service,
            ["msg-1", "msg-2"],
            add_label_ids=["TRASH"],
        )

        assert affected == 2
        assert service.users_api.messages_api.calls == [
            {
                "userId": "me",
                "body": {"ids": ["msg-1", "msg-2"], "addLabelIds": ["TRASH"]},
            }
        ]
