"""
Tests for Gmail Label Management Operations
--------------------------------------------
Tests for labels.py - managing Gmail labels.
"""

from unittest.mock import Mock, patch

import pytest

from app.core import state
from app.services.gmail.labels import (
    get_labels,
    create_label,
    delete_label,
    apply_label_to_senders_background,
    remove_label_from_senders_background,
    get_label_operation_status,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    state.reset_label_operation()
    yield
    state.reset_label_operation()


class TestGetLabels:
    """Tests for get_labels function."""

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should return error in result."""
        mock_get_service.return_value = (None, "Authentication required")

        result = get_labels()

        assert result["success"] is False
        assert result["error"] == "Authentication required"
        assert result["labels"] == []

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_successful_get_labels(self, mock_get_service):
        """Should return categorized labels."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": [
                {"id": "INBOX", "name": "INBOX", "type": "system"},
                {"id": "UNREAD", "name": "UNREAD", "type": "system"},
                {"id": "Label_1", "name": "Work", "type": "user"},
                {"id": "Label_2", "name": "Personal", "type": "user"},
            ]
        }

        result = get_labels()

        assert result["success"] is True
        assert result["error"] is None
        assert len(result["system_labels"]) == 2
        assert len(result["user_labels"]) == 2
        # User labels should be sorted alphabetically
        assert result["user_labels"][0]["name"] == "Personal"
        assert result["user_labels"][1]["name"] == "Work"

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_empty_labels(self, mock_get_service):
        """Empty labels list should return empty arrays."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": []
        }

        result = get_labels()

        assert result["success"] is True
        assert result["system_labels"] == []
        assert result["user_labels"] == []

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_exception_handling(self, mock_get_service):
        """Exception should return error."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.labels.return_value.list.return_value.execute.side_effect = Exception(
            "API Error"
        )

        result = get_labels()

        assert result["success"] is False
        assert result["error"] == "API Error"


class TestCreateLabel:
    """Tests for create_label function."""

    def test_empty_name(self):
        """Empty name should return error."""
        result = create_label("")

        assert result["success"] is False
        assert result["error"] == "Label name is required"
        assert result["label"] is None

    def test_whitespace_only_name(self):
        """Whitespace-only name should return error."""
        result = create_label("   ")

        assert result["success"] is False
        assert result["error"] == "Label name is required"

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should return error."""
        mock_get_service.return_value = (None, "Authentication required")

        result = create_label("Test Label")

        assert result["success"] is False
        assert result["error"] == "Authentication required"

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_successful_create(self, mock_get_service):
        """Successful create should return label info."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.labels.return_value.create.return_value.execute.return_value = {
            "id": "Label_123",
            "name": "Test Label",
            "type": "user",
        }

        result = create_label("Test Label")

        assert result["success"] is True
        assert result["error"] is None
        assert result["label"]["id"] == "Label_123"
        assert result["label"]["name"] == "Test Label"

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_label_already_exists(self, mock_get_service):
        """Duplicate label should return specific error."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.labels.return_value.create.return_value.execute.side_effect = Exception(
            "Label name exists or is reserved"
        )

        result = create_label("Test Label")

        assert result["success"] is False
        assert "already exists" in result["error"]

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_strips_whitespace(self, mock_get_service):
        """Should strip whitespace from label name."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.labels.return_value.create.return_value.execute.return_value = {
            "id": "Label_123",
            "name": "Test Label",
            "type": "user",
        }

        create_label("  Test Label  ")

        call_args = mock_service.users.return_value.labels.return_value.create.call_args
        assert call_args.kwargs["body"]["name"] == "Test Label"


class TestDeleteLabel:
    """Tests for delete_label function."""

    def test_empty_label_id(self):
        """Empty label ID should return error."""
        result = delete_label("")

        assert result["success"] is False
        assert result["error"] == "Label ID is required"

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should return error."""
        mock_get_service.return_value = (None, "Authentication required")

        result = delete_label("Label_123")

        assert result["success"] is False
        assert result["error"] == "Authentication required"

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_successful_delete(self, mock_get_service):
        """Successful delete should return success."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.labels.return_value.delete.return_value.execute.return_value = None

        result = delete_label("Label_123")

        assert result["success"] is True
        assert result["error"] is None

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_label_not_found(self, mock_get_service):
        """Not found label should return specific error."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.labels.return_value.delete.return_value.execute.side_effect = Exception(
            "Not Found"
        )

        result = delete_label("Label_123")

        assert result["success"] is False
        assert result["error"] == "Label not found"

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_cannot_delete_system_label(self, mock_get_service):
        """System label delete should return specific error."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.labels.return_value.delete.return_value.execute.side_effect = Exception(
            "Cannot delete system label"
        )

        result = delete_label("INBOX")

        assert result["success"] is False
        assert "system labels" in result["error"]


class TestApplyLabelToSendersBackground:
    """Tests for apply_label_to_senders_background function."""

    def test_empty_label_id(self):
        """Empty label ID should set error."""
        apply_label_to_senders_background("", ["sender@example.com"])

        status = get_label_operation_status()
        assert status["error"] == "Label ID is required"
        assert status["done"] is True

    def test_no_senders(self):
        """No senders should set error."""
        apply_label_to_senders_background("Label_123", [])

        status = get_label_operation_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should set error status."""
        mock_get_service.return_value = (None, "Authentication required")

        apply_label_to_senders_background("Label_123", ["sender@example.com"])

        status = get_label_operation_status()
        assert status["error"] == "Authentication required"
        assert status["done"] is True

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_no_emails_found(self, mock_get_service):
        """No emails should complete with message."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }

        apply_label_to_senders_background("Label_123", ["sender@example.com"])

        status = get_label_operation_status()
        assert status["done"] is True
        assert "No emails found" in status["message"]

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_successful_apply(self, mock_get_service):
        """Successful apply should update status."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": f"msg{i}"} for i in range(5)]
        }

        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        apply_label_to_senders_background("Label_123", ["sender@example.com"])

        status = get_label_operation_status()
        assert status["done"] is True
        assert status["error"] is None
        assert status["affected_count"] == 5
        assert "labeled" in status["message"].lower()

        # Verify addLabelIds was used
        call_args = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert "addLabelIds" in call_args.kwargs["body"]

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_pagination(self, mock_get_service):
        """Should handle paginated results."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        call_count = [0]

        def list_execute():
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "messages": [{"id": f"msg{i}"} for i in range(100)],
                    "nextPageToken": "token1",
                }
            else:
                return {"messages": [{"id": f"msg{i}"} for i in range(100, 150)]}

        mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = list_execute

        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        apply_label_to_senders_background("Label_123", ["sender@example.com"])

        status = get_label_operation_status()
        assert status["done"] is True
        assert status["affected_count"] == 150


class TestRemoveLabelFromSendersBackground:
    """Tests for remove_label_from_senders_background function."""

    def test_empty_label_id(self):
        """Empty label ID should set error."""
        remove_label_from_senders_background("", ["sender@example.com"])

        status = get_label_operation_status()
        assert status["error"] == "Label ID is required"
        assert status["done"] is True

    def test_no_senders(self):
        """No senders should set error."""
        remove_label_from_senders_background("Label_123", [])

        status = get_label_operation_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should set error status."""
        mock_get_service.return_value = (None, "Authentication required")

        remove_label_from_senders_background("Label_123", ["sender@example.com"])

        status = get_label_operation_status()
        assert status["error"] == "Authentication required"
        assert status["done"] is True

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_successful_remove(self, mock_get_service):
        """Successful remove should update status."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Mock label info fetch
        mock_service.users.return_value.labels.return_value.get.return_value.execute.return_value = {
            "id": "Label_123",
            "name": "TestLabel",
        }

        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": f"msg{i}"} for i in range(3)]
        }

        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        remove_label_from_senders_background("Label_123", ["sender@example.com"])

        status = get_label_operation_status()
        assert status["done"] is True
        assert status["error"] is None
        assert status["affected_count"] == 3
        assert "removed" in status["message"].lower() or "unlabeled" in status["message"].lower()

        # Verify removeLabelIds was used
        call_args = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert "removeLabelIds" in call_args.kwargs["body"]

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_label_fetch_error(self, mock_get_service):
        """Error fetching label should set error status."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.labels.return_value.get.return_value.execute.side_effect = Exception(
            "Label not found"
        )

        remove_label_from_senders_background("Label_123", ["sender@example.com"])

        status = get_label_operation_status()
        assert status["done"] is True
        assert "Failed to fetch label" in status["error"]

    @patch("app.services.gmail.labels.get_gmail_service")
    def test_no_emails_with_label(self, mock_get_service):
        """No emails with label should complete with message."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.labels.return_value.get.return_value.execute.return_value = {
            "id": "Label_123",
            "name": "TestLabel",
        }

        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }

        remove_label_from_senders_background("Label_123", ["sender@example.com"])

        status = get_label_operation_status()
        assert status["done"] is True
        assert "No emails found" in status["message"]


class TestGetLabelOperationStatus:
    """Tests for get_label_operation_status function."""

    def test_returns_copy(self):
        """get_label_operation_status should return a copy."""
        state.update_label_operation_status(message="Test")
        status1 = get_label_operation_status()
        status2 = get_label_operation_status()

        status1["message"] = "Modified"
        assert status2["message"] == "Test"

    def test_initial_state(self):
        """Initial state should have default values."""
        status = get_label_operation_status()
        assert status["done"] is False
        assert status["error"] is None
