# Test Suite Organization

This directory contains the test suite for the Gmail Cleaner application.

## Directory Structure

```text
tests/
├── __init__.py
├── conftest.py              # Pytest configuration and shared fixtures
├── unit/                    # Unit tests
│   ├── api/                # API endpoint tests
│   │   ├── test_api_actions.py
│   │   └── test_api_status.py
│   ├── models/             # Model/schema tests
│   │   └── test_schemas.py
│   └── services/          # Service layer tests
│       ├── auth/          # Authentication service tests
│       │   ├── test_oauth_flow_complete.py
│       │   ├── test_sign_in_api.py
│       │   ├── test_credentials_handling_complete.py
│       │   └── test_token_management_complete.py
│       └── gmail/         # Gmail service tests
│           └── test_gmail_service.py
└── integration/            # Integration tests
```

## Test Categories

### Unit Tests (`tests/unit/`)

Unit tests focus on testing individual components in isolation:

- **API** (`tests/unit/api/`): API endpoint tests
  - `test_api_actions.py`: POST action endpoints (scan, sign-in, unsubscribe, etc.)
  - `test_api_status.py`: GET status endpoints (status, results, auth-status, etc.)

- **Models** (`tests/unit/models/`): Model and schema validation tests
  - `test_schemas.py`: Pydantic model validation (FiltersModel, request/response schemas)

- **Services** (`tests/unit/services/`): Tests for service layer functions
  - **Auth** (`tests/unit/services/auth/`): Authentication-related tests
    - `test_oauth_flow_complete.py`: Complete OAuth flow scenarios
    - `test_sign_in_api.py`: Sign-in/sign-out API endpoint tests
    - `test_credentials_handling_complete.py`: Credentials file handling
    - `test_token_management_complete.py`: Token management scenarios
  - **Gmail** (`tests/unit/services/gmail/`): Gmail service tests
    - `test_gmail_service.py`: Gmail query building and email parsing helpers

### Integration Tests (`tests/integration/`)

Integration tests verify that multiple components work together correctly.

## Test Plan Coverage

The test suite covers scenarios from the test plan in `test-plan/01-authentication/`:

### OAuth Flow (`oauth-flow.md`)
- ✅ Successful OAuth flows (web auth, desktop mode, custom host)
- ✅ OAuth errors (cancellation, port conflicts, network failures, invalid codes, timeouts)
- ✅ Concurrent sign-in attempts
- ✅ Platform-specific behavior (Windows, macOS, Linux)

### Sign In/Out (`sign-in-out.md`)
- ✅ Sign-in operations and status checks
- ✅ Sign-out operations and state clearing
- ✅ Authentication state management
- ✅ API endpoint tests

### Credentials Handling (`credentials-handling.md`)
- ✅ Credentials file management
- ✅ Environment variable credentials
- ✅ Credentials validation
- ✅ Web auth mode credentials
- ✅ Security considerations

### Token Management (`token-management.md`)
- ✅ Token creation and storage
- ✅ Token validation and refresh
- ✅ Token file errors
- ✅ Token security

## Running Tests

Run all tests:

```bash
pytest
```

Run specific test file:

```bash
pytest tests/unit/services/auth/test_oauth_flow_complete.py
```

Run with coverage:

```bash
pytest --cov=app --cov-report=html
```

Run only unit tests:

```bash
pytest tests/unit/
```

Run only integration tests:

```bash
pytest tests/integration/
```

## Test Conventions

1. **Test Class Naming**: Use descriptive class names like `TestOAuthFlowErrors`
2. **Test Method Naming**: Use descriptive method names like `test_oauth_timeout_handling`
3. **Fixtures**: Shared fixtures are in `conftest.py`
4. **Mocking**: Use `unittest.mock` for isolating components
5. **Assertions**: Use clear assertion messages

## Adding New Tests

When adding new tests:

1. Place unit tests in `tests/unit/` under the appropriate subdirectory
2. Place integration tests in `tests/integration/`
3. Follow the existing naming conventions
4. Add appropriate docstrings
5. Ensure tests are isolated and don't depend on external services
6. Use fixtures from `conftest.py` when possible

## Notes

- All test files have been organized into the `tests/unit/` structure
- Legacy auth test files have been removed as they were replaced by the complete test files in `tests/unit/services/auth/`
- New tests should be added to the appropriate subdirectory in `tests/unit/` or `tests/integration/`
- All tests should pass before committing changes
