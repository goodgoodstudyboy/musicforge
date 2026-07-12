from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Stable error envelope shared by stores and interface adapters."""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        http_status: int = 400,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = str(error_code)
        self.message = str(message)
        self.http_status = int(http_status)
        self.retryable = bool(retryable)
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "http_status": self.http_status,
            "retryable": self.retryable,
            "details": self.details,
        }
