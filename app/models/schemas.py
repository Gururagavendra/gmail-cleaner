"""
Pydantic Models - Request/Response Schemas
------------------------------------------
Data validation and serialization.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator
import re


# ----- Filter Model -----

class FiltersModel(BaseModel):
    """Gmail filter options with validation."""
    older_than: Optional[str] = Field(default=None, description="Filter emails older than (e.g., 7d, 30d, 90d, 180d, 365d)")
    after_date: Optional[str] = Field(default=None, description="Filter emails after this date (format: YYYY/MM/DD)")
    before_date: Optional[str] = Field(default=None, description="Filter emails before this date (format: YYYY/MM/DD)")
    larger_than: Optional[str] = Field(default=None, description="Filter emails larger than (e.g., 1M, 5M, 10M)")
    category: Optional[str] = Field(default=None, description="Gmail category filter")
    sender: Optional[str] = Field(default=None, description="Filter emails from specific sender (email address or domain)")
    
    @field_validator('older_than')
    @classmethod
    def validate_older_than(cls, v):
        if v is None or v == '':
            return None
        if not re.match(r'^\d+d$', v):
            raise ValueError('older_than must be in format like "7d", "30d", "365d"')
        return v
    
    @field_validator('after_date')
    @classmethod
    def validate_after_date(cls, v):
        if v is None or v == '':
            return None
        if not re.match(r'^\d{4}/\d{2}/\d{2}$', v):
            raise ValueError('after_date must be in format like "2025/01/15"')
        return v
    
    @field_validator('before_date')
    @classmethod
    def validate_before_date(cls, v):
        if v is None or v == '':
            return None
        if not re.match(r'^\d{4}/\d{2}/\d{2}$', v):
            raise ValueError('before_date must be in format like "2025/01/15"')
        return v
    
    @field_validator('larger_than')
    @classmethod
    def validate_larger_than(cls, v):
        if v is None or v == '':
            return None
        if not re.match(r'^\d+[KMG]$', v, re.IGNORECASE):
            raise ValueError('larger_than must be in format like "1M", "5M", "10M"')
        return v
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        if v is None or v == '':
            return None
        allowed = ['primary', 'social', 'promotions', 'updates', 'forums']
        if v.lower() not in allowed:
            raise ValueError(f'category must be one of: {allowed}')
        return v.lower()
    
    @field_validator('sender')
    @classmethod
    def validate_sender(cls, v):
        if v is None or v == '':
            return None
        # Allow email addresses or domain names
        sender = v.strip()
        if not sender:
            return None
        # Basic validation: must contain @ or be a domain-like string
        if '@' not in sender and '.' not in sender:
            raise ValueError('sender must be a valid email address or domain')
        return sender


# ----- Request Models -----

class ScanRequest(BaseModel):
    """Request to start email scan."""
    limit: int = Field(default=500, ge=1, le=5000, description="Max emails to scan")
    filters: Optional[FiltersModel] = Field(default=None, description="Gmail filter options")


class MarkReadRequest(BaseModel):
    """Request to mark emails as read."""
    count: int = Field(default=100, ge=1, le=100000, description="Number of emails to mark")
    filters: Optional[FiltersModel] = Field(default=None, description="Gmail filter options")


class DeleteScanRequest(BaseModel):
    """Request to scan senders for deletion."""
    limit: int = Field(default=1000, ge=1, le=10000, description="Max emails to scan")
    filters: Optional[FiltersModel] = Field(default=None, description="Gmail filter options")


class UnsubscribeRequest(BaseModel):
    """Request to unsubscribe from a sender."""
    domain: str = Field(default="", description="Sender domain")
    link: str = Field(default="", description="Unsubscribe link URL")


class DeleteEmailsRequest(BaseModel):
    """Request to delete emails from a sender."""
    sender: str = Field(default="", description="Sender email address")


class DeleteBulkRequest(BaseModel):
    """Request to delete emails from multiple senders."""
    senders: list[str] = Field(default=[], max_length=50, description="List of sender addresses (max 50)")


class DownloadEmailsRequest(BaseModel):
    """Request to download emails from selected senders."""
    senders: list[str] = Field(default=[], max_length=50, description="List of sender addresses (max 50)")


# ----- Response Models -----

class StatusResponse(BaseModel):
    """Generic status response."""
    status: str


class AuthStatusResponse(BaseModel):
    """Authentication status response."""
    email: Optional[str] = None
    logged_in: bool = False


class ScanStatusResponse(BaseModel):
    """Scan progress status response."""
    progress: int = 0
    message: str = "Ready"
    done: bool = False
    error: Optional[str] = None


class UnreadCountResponse(BaseModel):
    """Unread email count response."""
    count: int = 0
    error: Optional[str] = None


class UnsubscribeResponse(BaseModel):
    """Unsubscribe action response."""
    success: bool
    message: str
    domain: Optional[str] = None


class DeleteResponse(BaseModel):
    """Delete action response."""
    success: bool
    deleted: int = 0
    message: Optional[str] = None
