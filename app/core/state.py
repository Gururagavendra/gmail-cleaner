"""
Global Application State
------------------------
Thread-safe shared state across the application.

All state access is protected by locks to prevent race conditions
when multiple background tasks run concurrently.
"""

import threading
from copy import deepcopy
from typing import Any


class AppState:
    """Thread-safe global application state container.

    All state access and modification is protected by locks to prevent
    race conditions when background tasks modify state concurrently.

    Usage:
        # Reading state (returns a copy, safe to use without locks)
        status = state.get_scan_status()

        # Updating state (thread-safe)
        state.update_scan_status(progress=50, message="Scanning...")

        # Resetting state (thread-safe)
        state.reset_scan()
    """

    def __init__(self) -> None:
        # === Locks for thread safety ===
        self._user_lock = threading.Lock()
        self._scan_lock = threading.Lock()
        self._mark_read_lock = threading.Lock()
        self._delete_scan_lock = threading.Lock()
        self._delete_bulk_lock = threading.Lock()
        self._download_lock = threading.Lock()
        self._auth_lock = threading.Lock()
        self._label_lock = threading.Lock()
        self._archive_lock = threading.Lock()
        self._important_lock = threading.Lock()
        self._unread_scan_lock = threading.Lock()
        self._unread_action_lock = threading.Lock()

        # === User state ===
        self._current_user: dict = {"email": None, "logged_in": False}

        # === Scan state ===
        self._scan_results: list = []
        self._scan_status: dict = {
            "progress": 0,
            "message": "Ready",
            "done": False,
            "error": None,
        }

        # === Mark read state ===
        self._mark_read_status: dict = {
            "progress": 0,
            "message": "Ready",
            "done": False,
            "error": None,
            "marked_count": 0,
        }

        # === Delete state ===
        self._delete_scan_results: list = []
        self._delete_scan_status: dict = {
            "progress": 0,
            "message": "Ready",
            "done": False,
            "error": None,
        }

        # === Delete bulk operation state ===
        self._delete_bulk_status: dict = {
            "progress": 0,
            "message": "Ready",
            "done": False,
            "error": None,
            "deleted_count": 0,
            "total_senders": 0,
            "current_sender": 0,
        }

        # === Download emails state ===
        self._download_status: dict = {
            "progress": 0,
            "message": "Ready",
            "done": False,
            "error": None,
            "total_emails": 0,
            "fetched_count": 0,
            "csv_data": None,
        }

        # === Auth state ===
        self._pending_auth_url: dict = {"url": None}
        self._pending_auth_code: dict = {"code": None}
        self._oauth_state: dict = {"state": None}

        # === Label operation state ===
        self._label_operation_status: dict = {
            "progress": 0,
            "message": "Ready",
            "done": False,
            "error": None,
            "affected_count": 0,
            "total_senders": 0,
            "current_sender": 0,
        }

        # === Archive state ===
        self._archive_status: dict = {
            "progress": 0,
            "message": "Ready",
            "done": False,
            "error": None,
            "archived_count": 0,
            "total_senders": 0,
            "current_sender": 0,
        }

        # === Mark important state ===
        self._important_status: dict = {
            "progress": 0,
            "message": "Ready",
            "done": False,
            "error": None,
            "affected_count": 0,
            "total_senders": 0,
            "current_sender": 0,
        }

        # === Unread scan state ===
        self._unread_scan_results: list = []
        self._unread_scan_status: dict = {
            "progress": 0,
            "message": "Ready",
            "done": False,
            "error": None,
        }

        # === Unread action state (mark read/archive) ===
        self._unread_action_status: dict = {
            "progress": 0,
            "message": "Ready",
            "done": False,
            "error": None,
            "affected_count": 0,
            "total_senders": 0,
            "current_sender": 0,
        }

    # =========================================================================
    # USER STATE
    # =========================================================================

    def get_current_user(self) -> dict:
        """Get a copy of the current user state."""
        with self._user_lock:
            return self._current_user.copy()

    def update_current_user(self, **kwargs: Any) -> None:
        """Update current user state with the provided key-value pairs."""
        with self._user_lock:
            self._current_user.update(kwargs)

    def set_current_user(self, user: dict) -> None:
        """Replace the current user state entirely."""
        with self._user_lock:
            self._current_user = user.copy()

    # =========================================================================
    # SCAN STATE
    # =========================================================================

    def get_scan_status(self) -> dict:
        """Get a copy of the scan status."""
        with self._scan_lock:
            return self._scan_status.copy()

    def update_scan_status(self, **kwargs: Any) -> None:
        """Update scan status with the provided key-value pairs."""
        with self._scan_lock:
            self._scan_status.update(kwargs)

    def get_scan_results(self) -> list:
        """Get a deep copy of the scan results."""
        with self._scan_lock:
            return deepcopy(self._scan_results)

    def set_scan_results(self, results: list) -> None:
        """Replace the scan results entirely."""
        with self._scan_lock:
            self._scan_results = deepcopy(results)

    def append_scan_result(self, result: dict) -> None:
        """Append a single result to scan results."""
        with self._scan_lock:
            self._scan_results.append(deepcopy(result))

    def extend_scan_results(self, results: list) -> None:
        """Extend scan results with multiple items."""
        with self._scan_lock:
            self._scan_results.extend(deepcopy(results))

    def reset_scan(self) -> None:
        """Reset scan state."""
        with self._scan_lock:
            self._scan_results = []
            self._scan_status = {
                "progress": 0,
                "message": "Ready",
                "done": False,
                "error": None,
            }

    # =========================================================================
    # MARK READ STATE
    # =========================================================================

    def get_mark_read_status(self) -> dict:
        """Get a copy of the mark read status."""
        with self._mark_read_lock:
            return self._mark_read_status.copy()

    def update_mark_read_status(self, **kwargs: Any) -> None:
        """Update mark read status with the provided key-value pairs."""
        with self._mark_read_lock:
            self._mark_read_status.update(kwargs)

    def reset_mark_read(self) -> None:
        """Reset mark read state."""
        with self._mark_read_lock:
            self._mark_read_status = {
                "progress": 0,
                "message": "Ready",
                "done": False,
                "error": None,
                "marked_count": 0,
            }

    # =========================================================================
    # DELETE SCAN STATE
    # =========================================================================

    def get_delete_scan_status(self) -> dict:
        """Get a copy of the delete scan status."""
        with self._delete_scan_lock:
            return self._delete_scan_status.copy()

    def update_delete_scan_status(self, **kwargs: Any) -> None:
        """Update delete scan status with the provided key-value pairs."""
        with self._delete_scan_lock:
            self._delete_scan_status.update(kwargs)

    def get_delete_scan_results(self) -> list:
        """Get a deep copy of the delete scan results."""
        with self._delete_scan_lock:
            return deepcopy(self._delete_scan_results)

    def set_delete_scan_results(self, results: list) -> None:
        """Replace the delete scan results entirely."""
        with self._delete_scan_lock:
            self._delete_scan_results = deepcopy(results)

    def append_delete_scan_result(self, result: dict) -> None:
        """Append a single result to delete scan results."""
        with self._delete_scan_lock:
            self._delete_scan_results.append(deepcopy(result))

    def extend_delete_scan_results(self, results: list) -> None:
        """Extend delete scan results with multiple items."""
        with self._delete_scan_lock:
            self._delete_scan_results.extend(deepcopy(results))

    def reset_delete_scan(self) -> None:
        """Reset delete scan state."""
        with self._delete_scan_lock:
            self._delete_scan_results = []
            self._delete_scan_status = {
                "progress": 0,
                "message": "Ready",
                "done": False,
                "error": None,
            }

    # =========================================================================
    # DELETE BULK STATE
    # =========================================================================

    def get_delete_bulk_status(self) -> dict:
        """Get a copy of the delete bulk status."""
        with self._delete_bulk_lock:
            return self._delete_bulk_status.copy()

    def update_delete_bulk_status(self, **kwargs: Any) -> None:
        """Update delete bulk status with the provided key-value pairs."""
        with self._delete_bulk_lock:
            self._delete_bulk_status.update(kwargs)

    def reset_delete_bulk(self) -> None:
        """Reset delete bulk state."""
        with self._delete_bulk_lock:
            self._delete_bulk_status = {
                "progress": 0,
                "message": "Ready",
                "done": False,
                "error": None,
                "deleted_count": 0,
                "total_senders": 0,
                "current_sender": 0,
            }

    # =========================================================================
    # DOWNLOAD STATE
    # =========================================================================

    def get_download_status(self) -> dict:
        """Get a copy of the download status."""
        with self._download_lock:
            return self._download_status.copy()

    def update_download_status(self, **kwargs: Any) -> None:
        """Update download status with the provided key-value pairs."""
        with self._download_lock:
            self._download_status.update(kwargs)

    def reset_download(self) -> None:
        """Reset download state."""
        with self._download_lock:
            self._download_status = {
                "progress": 0,
                "message": "Ready",
                "done": False,
                "error": None,
                "total_emails": 0,
                "fetched_count": 0,
                "csv_data": None,
            }

    # =========================================================================
    # AUTH STATE
    # =========================================================================

    def get_pending_auth_url(self) -> dict:
        """Get a copy of the pending auth URL."""
        with self._auth_lock:
            return self._pending_auth_url.copy()

    def set_pending_auth_url(self, url: str | None) -> None:
        """Set the pending auth URL."""
        with self._auth_lock:
            self._pending_auth_url["url"] = url

    def get_pending_auth_code(self) -> dict:
        """Get a copy of the pending auth code."""
        with self._auth_lock:
            return self._pending_auth_code.copy()

    def set_pending_auth_code(self, code: str | None) -> None:
        """Set the pending auth code."""
        with self._auth_lock:
            self._pending_auth_code["code"] = code

    def get_oauth_state(self) -> dict:
        """Get a copy of the OAuth state."""
        with self._auth_lock:
            return self._oauth_state.copy()

    def set_oauth_state(self, oauth_state: str | None) -> None:
        """Set the OAuth state value."""
        with self._auth_lock:
            self._oauth_state["state"] = oauth_state

    # =========================================================================
    # LABEL OPERATION STATE
    # =========================================================================

    def get_label_operation_status(self) -> dict:
        """Get a copy of the label operation status."""
        with self._label_lock:
            return self._label_operation_status.copy()

    def update_label_operation_status(self, **kwargs: Any) -> None:
        """Update label operation status with the provided key-value pairs."""
        with self._label_lock:
            self._label_operation_status.update(kwargs)

    def reset_label_operation(self) -> None:
        """Reset label operation state."""
        with self._label_lock:
            self._label_operation_status = {
                "progress": 0,
                "message": "Ready",
                "done": False,
                "error": None,
                "affected_count": 0,
                "total_senders": 0,
                "current_sender": 0,
            }

    # =========================================================================
    # ARCHIVE STATE
    # =========================================================================

    def get_archive_status(self) -> dict:
        """Get a copy of the archive status."""
        with self._archive_lock:
            return self._archive_status.copy()

    def update_archive_status(self, **kwargs: Any) -> None:
        """Update archive status with the provided key-value pairs."""
        with self._archive_lock:
            self._archive_status.update(kwargs)

    def reset_archive(self) -> None:
        """Reset archive state."""
        with self._archive_lock:
            self._archive_status = {
                "progress": 0,
                "message": "Ready",
                "done": False,
                "error": None,
                "archived_count": 0,
                "total_senders": 0,
                "current_sender": 0,
            }

    # =========================================================================
    # MARK IMPORTANT STATE
    # =========================================================================

    def get_important_status(self) -> dict:
        """Get a copy of the mark important status."""
        with self._important_lock:
            return self._important_status.copy()

    def update_important_status(self, **kwargs: Any) -> None:
        """Update mark important status with the provided key-value pairs."""
        with self._important_lock:
            self._important_status.update(kwargs)

    def reset_important(self) -> None:
        """Reset mark important state."""
        with self._important_lock:
            self._important_status = {
                "progress": 0,
                "message": "Ready",
                "done": False,
                "error": None,
                "affected_count": 0,
                "total_senders": 0,
                "current_sender": 0,
            }

    # =========================================================================
    # UNREAD SCAN STATE
    # =========================================================================

    def get_unread_scan_status(self) -> dict:
        """Get a copy of the unread scan status."""
        with self._unread_scan_lock:
            return self._unread_scan_status.copy()

    def update_unread_scan_status(self, **kwargs: Any) -> None:
        """Update unread scan status with the provided key-value pairs."""
        with self._unread_scan_lock:
            self._unread_scan_status.update(kwargs)

    def get_unread_scan_results(self) -> list:
        """Get a deep copy of the unread scan results."""
        with self._unread_scan_lock:
            return deepcopy(self._unread_scan_results)

    def set_unread_scan_results(self, results: list) -> None:
        """Replace the unread scan results entirely."""
        with self._unread_scan_lock:
            self._unread_scan_results = deepcopy(results)

    def remove_senders_from_unread_results(self, senders: set[str]) -> None:
        """Atomically remove senders from unread scan results.

        This performs a read-filter-write operation under a single lock
        to prevent race conditions with concurrent scans/actions.

        Args:
            senders: Set of sender email addresses to remove
        """
        with self._unread_scan_lock:
            self._unread_scan_results = [
                r for r in self._unread_scan_results if r.get("email") not in senders
            ]

    def reset_unread_scan(self) -> None:
        """Reset unread scan state."""
        with self._unread_scan_lock:
            self._unread_scan_results = []
            self._unread_scan_status = {
                "progress": 0,
                "message": "Ready",
                "done": False,
                "error": None,
            }

    # =========================================================================
    # UNREAD ACTION STATE
    # =========================================================================

    def get_unread_action_status(self) -> dict:
        """Get a copy of the unread action status."""
        with self._unread_action_lock:
            return self._unread_action_status.copy()

    def update_unread_action_status(self, **kwargs: Any) -> None:
        """Update unread action status with the provided key-value pairs."""
        with self._unread_action_lock:
            self._unread_action_status.update(kwargs)

    def reset_unread_action(self) -> None:
        """Reset unread action state."""
        with self._unread_action_lock:
            self._unread_action_status = {
                "progress": 0,
                "message": "Ready",
                "done": False,
                "error": None,
                "affected_count": 0,
                "total_senders": 0,
                "current_sender": 0,
            }

    # =========================================================================
    # BACKWARD COMPATIBILITY PROPERTIES
    # =========================================================================
    # These properties maintain backward compatibility with code that directly
    # accesses state attributes. They should be migrated to use the thread-safe
    # methods above, but are provided to prevent breaking changes.
    #
    # WARNING: Direct property access is NOT thread-safe for mutations.
    # Use the thread-safe methods (get_*, update_*, set_*) instead.

    @property
    def current_user(self) -> dict:
        """Backward compatible access. Prefer get_current_user()."""
        return self.get_current_user()

    @current_user.setter
    def current_user(self, value: dict) -> None:
        """Backward compatible setter. Prefer set_current_user()."""
        self.set_current_user(value)

    @property
    def scan_results(self) -> list:
        """Backward compatible access. Prefer get_scan_results()."""
        return self.get_scan_results()

    @scan_results.setter
    def scan_results(self, value: list) -> None:
        """Backward compatible setter. Prefer set_scan_results()."""
        self.set_scan_results(value)

    @property
    def scan_status(self) -> dict:
        """Backward compatible access. Prefer get_scan_status()."""
        return self.get_scan_status()

    @scan_status.setter
    def scan_status(self, value: dict) -> None:
        """Backward compatible setter."""
        with self._scan_lock:
            self._scan_status = value.copy()

    @property
    def mark_read_status(self) -> dict:
        """Backward compatible access. Prefer get_mark_read_status()."""
        return self.get_mark_read_status()

    @mark_read_status.setter
    def mark_read_status(self, value: dict) -> None:
        """Backward compatible setter."""
        with self._mark_read_lock:
            self._mark_read_status = value.copy()

    @property
    def delete_scan_results(self) -> list:
        """Backward compatible access. Prefer get_delete_scan_results()."""
        return self.get_delete_scan_results()

    @delete_scan_results.setter
    def delete_scan_results(self, value: list) -> None:
        """Backward compatible setter."""
        self.set_delete_scan_results(value)

    @property
    def delete_scan_status(self) -> dict:
        """Backward compatible access. Prefer get_delete_scan_status()."""
        return self.get_delete_scan_status()

    @delete_scan_status.setter
    def delete_scan_status(self, value: dict) -> None:
        """Backward compatible setter."""
        with self._delete_scan_lock:
            self._delete_scan_status = value.copy()

    @property
    def delete_bulk_status(self) -> dict:
        """Backward compatible access. Prefer get_delete_bulk_status()."""
        return self.get_delete_bulk_status()

    @delete_bulk_status.setter
    def delete_bulk_status(self, value: dict) -> None:
        """Backward compatible setter."""
        with self._delete_bulk_lock:
            self._delete_bulk_status = value.copy()

    @property
    def download_status(self) -> dict:
        """Backward compatible access. Prefer get_download_status()."""
        return self.get_download_status()

    @download_status.setter
    def download_status(self, value: dict) -> None:
        """Backward compatible setter."""
        with self._download_lock:
            self._download_status = value.copy()

    @property
    def pending_auth_url(self) -> dict:
        """Backward compatible access. Prefer get_pending_auth_url()."""
        return self.get_pending_auth_url()

    @pending_auth_url.setter
    def pending_auth_url(self, value: dict) -> None:
        """Backward compatible setter."""
        with self._auth_lock:
            self._pending_auth_url = value.copy()

    @property
    def pending_auth_code(self) -> dict:
        """Backward compatible access. Prefer get_pending_auth_code()."""
        return self.get_pending_auth_code()

    @pending_auth_code.setter
    def pending_auth_code(self, value: dict) -> None:
        """Backward compatible setter."""
        with self._auth_lock:
            self._pending_auth_code = value.copy()

    @property
    def oauth_state(self) -> dict:
        """Backward compatible access. Prefer get_oauth_state()."""
        return self.get_oauth_state()

    @oauth_state.setter
    def oauth_state(self, value: dict) -> None:
        """Backward compatible setter."""
        with self._auth_lock:
            self._oauth_state = value.copy()

    @property
    def oauth_state_lock(self) -> threading.Lock:
        """Backward compatible access to auth lock."""
        return self._auth_lock

    @property
    def label_operation_status(self) -> dict:
        """Backward compatible access. Prefer get_label_operation_status()."""
        return self.get_label_operation_status()

    @label_operation_status.setter
    def label_operation_status(self, value: dict) -> None:
        """Backward compatible setter."""
        with self._label_lock:
            self._label_operation_status = value.copy()

    @property
    def archive_status(self) -> dict:
        """Backward compatible access. Prefer get_archive_status()."""
        return self.get_archive_status()

    @archive_status.setter
    def archive_status(self, value: dict) -> None:
        """Backward compatible setter."""
        with self._archive_lock:
            self._archive_status = value.copy()

    @property
    def important_status(self) -> dict:
        """Backward compatible access. Prefer get_important_status()."""
        return self.get_important_status()

    @important_status.setter
    def important_status(self, value: dict) -> None:
        """Backward compatible setter."""
        with self._important_lock:
            self._important_status = value.copy()


# Global state instance
state = AppState()
