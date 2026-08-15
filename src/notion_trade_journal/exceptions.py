from __future__ import annotations

"""Custom exceptions for the trade journal integration."""


class TradeJournalError(Exception):
    """Base exception for the project."""


class TradeJournalConfigurationError(TradeJournalError):
    """Raised when required environment or runtime configuration is missing."""


class NotionAPIError(TradeJournalError):
    """Raised when the Notion API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None, code: str | None = None):
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class TradeJournalSchemaError(TradeJournalError):
    """Raised when the Notion database/data source schema does not match expectations."""


class TradeJournalValidationError(TradeJournalError):
    """Raised when trade payload content cannot be normalized into a valid entry."""


class TradeJournalDuplicateError(TradeJournalError):
    """Raised when a trade matches an existing duplicate key in the journal."""


class TradeJournalSyncError(TradeJournalError):
    """Raised when a downstream sync fails after the Notion write succeeds."""


class SupabaseAPIError(TradeJournalError):
    """Raised when the Supabase REST API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None, code: str | None = None):
        self.status_code = status_code
        self.code = code
        super().__init__(message)
