from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.errors import DuplicateInvoiceError, InvoiceNotFoundError
from app.models.invoice import Invoice, InvoiceStatus
from app.schemas.invoice import InvoiceCreate
from app.services.invoice import InvoiceService


class FakeInvoiceRepository:
    """In-memory stand-in for InvoiceRepository used in unit tests."""

    def __init__(self) -> None:
        self.invoices: dict[int, Invoice] = {}
        self._next_id = 1

    def create(self, invoice: Invoice) -> Invoice:
        invoice.id = self._next_id
        self._next_id += 1
        self.invoices[invoice.id] = invoice
        return invoice

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        return self.invoices.get(invoice_id)

    def get_by_number(self, invoice_number: str) -> Invoice | None:
        return next(
            (i for i in self.invoices.values() if i.invoice_number == invoice_number),
            None,
        )

    def list(self, limit: int, offset: int) -> list[Invoice]:
        return list(self.invoices.values())[offset : offset + limit]

    def count(self) -> int:
        return len(self.invoices)


@pytest.fixture
def repository() -> FakeInvoiceRepository:
    return FakeInvoiceRepository()


@pytest.fixture
def service(repository: FakeInvoiceRepository) -> InvoiceService:
    return InvoiceService(repository)


def make_payload(invoice_number: str = "INV-001") -> InvoiceCreate:
    return InvoiceCreate(
        invoice_number=invoice_number,
        customer_name="Ada Lovelace",
        customer_email="ada@example.com",
        amount=Decimal("1250.50"),
        issued_at=date(2026, 1, 15),
    )


def test_create_invoice_persists_and_returns_invoice(service: InvoiceService) -> None:
    invoice = service.create_invoice(make_payload())

    assert invoice.id is not None
    assert invoice.invoice_number == "INV-001"
    assert invoice.amount == Decimal("1250.50")
    assert invoice.status == InvoiceStatus.ISSUED


def test_create_invoice_normalizes_invoice_number(service: InvoiceService) -> None:
    invoice = service.create_invoice(make_payload("  inv-001  "))

    assert invoice.invoice_number == "INV-001"


def test_create_invoice_raises_on_duplicate_number(service: InvoiceService) -> None:
    service.create_invoice(make_payload("INV-001"))

    with pytest.raises(DuplicateInvoiceError):
        service.create_invoice(make_payload("INV-001"))


def test_create_invoice_raises_on_duplicate_number_case_insensitive(
    service: InvoiceService,
) -> None:
    service.create_invoice(make_payload("INV-001"))

    with pytest.raises(DuplicateInvoiceError):
        service.create_invoice(make_payload("inv-001"))


def test_get_invoice_raises_when_not_found(service: InvoiceService) -> None:
    with pytest.raises(InvoiceNotFoundError):
        service.get_invoice(999)


def test_get_invoice_returns_existing_invoice(service: InvoiceService) -> None:
    created = service.create_invoice(make_payload())

    assert service.get_invoice(created.id).id == created.id


def test_list_invoices_returns_items_and_total(service: InvoiceService) -> None:
    for index in range(3):
        service.create_invoice(make_payload(f"INV-{index:03d}"))

    items, total = service.list_invoices(limit=2, offset=0)

    assert len(items) == 2
    assert total == 3


def test_invoice_create_rejects_amount_with_more_than_two_decimals() -> None:
    with pytest.raises(ValidationError):
        InvoiceCreate(
            invoice_number="INV-001",
            customer_name="Ada Lovelace",
            customer_email="ada@example.com",
            amount=Decimal("10.999"),
            issued_at=date(2026, 1, 15),
        )


def test_invoice_create_rejects_amount_with_too_many_digits() -> None:
    with pytest.raises(ValidationError):
        InvoiceCreate(
            invoice_number="INV-001",
            customer_name="Ada Lovelace",
            customer_email="ada@example.com",
            amount=Decimal("1234567890123.00"),
            issued_at=date(2026, 1, 15),
        )


def test_invoice_create_rejects_non_positive_amount() -> None:
    with pytest.raises(ValidationError):
        InvoiceCreate(
            invoice_number="INV-001",
            customer_name="Ada Lovelace",
            customer_email="ada@example.com",
            amount=Decimal("0"),
            issued_at=date(2026, 1, 15),
        )


def test_invoice_create_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        InvoiceCreate(
            invoice_number="INV-001",
            customer_name="Ada Lovelace",
            customer_email="ada@example.com",
            amount=Decimal("1250.50"),
            status="cancelled",
            issued_at=date(2026, 1, 15),
        )


def test_invoice_create_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        InvoiceCreate(
            invoice_number="INV-001",
            customer_name="Ada Lovelace",
            customer_email="not-an-email",
            amount=Decimal("1250.50"),
            issued_at=date(2026, 1, 15),
        )
