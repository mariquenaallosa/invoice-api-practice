from app.core.errors import AppError, DuplicateInvoiceError, InvoiceNotFoundError


def test_app_error_uses_class_level_defaults() -> None:
    error = AppError("something went wrong")

    assert error.status_code == 500
    assert error.code == "internal_error"
    assert error.message == "something went wrong"
    assert error.details is None


def test_app_error_accepts_status_and_code_overrides() -> None:
    error = AppError("teapot", status_code=418, code="teapot_error", details={"a": 1})

    assert error.status_code == 418
    assert error.code == "teapot_error"
    assert error.details == {"a": 1}


def test_invoice_not_found_error_carries_the_invoice_id() -> None:
    error = InvoiceNotFoundError(42)

    assert error.status_code == 404
    assert error.code == "invoice_not_found"
    assert "42" in error.message


def test_duplicate_invoice_error_carries_the_invoice_number() -> None:
    error = DuplicateInvoiceError("INV-001")

    assert error.status_code == 409
    assert error.code == "invoice_duplicate"
    assert "INV-001" in error.message
