"""
Pytest Configuration and Fixtures
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def sample_email_headers():
    """Sample email headers for testing."""
    return [
        {'name': 'From', 'value': 'Newsletter <newsletter@example.com>'},
        {'name': 'Subject', 'value': 'Test Email Subject'},
        {'name': 'List-Unsubscribe', 'value': '<https://example.com/unsubscribe>'},
    ]


@pytest.fixture
def sample_email_headers_one_click():
    """Sample email headers with one-click unsubscribe."""
    return [
        {'name': 'From', 'value': 'Marketing <marketing@company.com>'},
        {'name': 'Subject', 'value': 'Special Offer'},
        {'name': 'List-Unsubscribe', 'value': '<https://company.com/unsub?id=123>'},
        {'name': 'List-Unsubscribe-Post', 'value': 'List-Unsubscribe=One-Click'},
    ]
