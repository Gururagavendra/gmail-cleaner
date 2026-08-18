"""
Rate Limiting Configuration
---------------------------
Configure rate limiting for API endpoints using slowapi.

This module provides protection against:
- DoS attacks
- Accidental API quota exhaustion
- Runaway client requests
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Create the limiter instance with IP-based rate limiting
# Using in-memory storage (suitable for single-instance local tool)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],  # Default: 60 requests per minute
    storage_uri="memory://",
)

# Rate limit configurations for different endpoint types
# Status endpoints: Higher limit for frequent polling (e.g., progress updates)
STATUS_RATE_LIMIT = "120/minute"

# Action endpoints: Lower limit for write operations
ACTION_RATE_LIMIT = "30/minute"

# Auth endpoints: Moderate limit
AUTH_RATE_LIMIT = "10/minute"

# Scan/delete operations: Very limited (heavy operations)
HEAVY_OPERATION_RATE_LIMIT = "10/minute"
