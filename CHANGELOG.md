# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- **Thread-Safe State Management**: Added `threading.Lock` synchronization to `AppState` class to prevent race conditions in concurrent operations
- **Gmail Query Injection Prevention**: Added `sanitize_gmail_query_value()` function to properly escape user-supplied values in Gmail API queries
- **API Rate Limiting**: Added `slowapi` middleware with tiered rate limits:
  - Status endpoints: 120 req/min
  - Action endpoints: 30 req/min
  - Auth endpoints: 10 req/min
  - Heavy operations: 10 req/min

### Added
- CodeRabbit AI code review integration with `.coderabbit.yaml` configuration
- Pre-commit hooks for code quality checks (ruff, bandit, trailing whitespace, etc.)
- Comprehensive type annotations throughout the codebase
- 33 new mock-based tests for `delete.py` (81% coverage)
- 12 new mock-based tests for `scan.py` (84% coverage)
- 13 new tests for query sanitization function
- `slowapi` dependency for rate limiting

### Changed
- Updated pre-commit hook versions to latest stable releases
- Improved code formatting consistency (double quotes, trailing commas, whitespace)
- Enhanced function signatures with multiline formatting for better readability
- Normalized code style across Python, JavaScript, CSS, and HTML files
- All Gmail service files now use thread-safe state methods instead of direct dictionary mutation
- Auth modules updated to use thread-safe state access patterns
- API action handlers use `body` parameter name to avoid FastAPI `Request` conflicts

### Fixed
- Timezone handling in CSV filename generation (now uses UTC)
- Missing return type annotations in multiple functions
- Closure variable binding in batch callback functions
- Test coverage improvements with proper mock assertions
- Boolean positional argument pattern in `mark_important_background`
- Race condition vulnerability in global state management
- State mutation bug where property accessors returned copies (mutations were discarded)
- All 192 tests now passing (up from 178 with 2 failures)

## [1.0.0] - 2024-11-29

### Added
- Initial release
- Bulk unsubscribe functionality with one-click support
- Delete emails by sender with bulk operations
- Mark emails as read in bulk
- Smart filtering options (age, size, category, sender, label)
- Docker support for all platforms
- Gmail API integration with batch requests
- Privacy-first architecture (runs 100% locally)
- Gmail-style user interface
- Label management (create, apply, remove)
- Archive emails functionality
- Mark emails as important/unimportant
- Download emails as CSV export

[Unreleased]: https://github.com/Gururagavendra/gmail-cleaner/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Gururagavendra/gmail-cleaner/releases/tag/v1.0.0
