from typing import Any


class AppError(Exception):
    """Base class for domain errors that map to an HTTP response."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: Any | None = None,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class InvoiceNotFoundError(AppError):
    status_code = 404
    code = "invoice_not_found"

    def __init__(self, invoice_id: int) -> None:
        super().__init__(f"Invoice with id {invoice_id} was not found.")


class DuplicateInvoiceError(AppError):
    status_code = 409
    code = "invoice_duplicate"

    def __init__(self, invoice_number: str) -> None:
        super().__init__(f"Invoice number '{invoice_number}' already exists.")
