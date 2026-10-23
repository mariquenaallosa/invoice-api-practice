from decimal import Decimal

from app.core.errors import DuplicateInvoiceError, InvoiceNotFoundError
from app.models.invoice import Invoice
from app.repositories.invoice import InvoiceRepository
from app.schemas.invoice import InvoiceCreate


class InvoiceService:
    """Business rules for invoices."""

    def __init__(self, repository: InvoiceRepository) -> None:
        self.repository = repository

    def create_invoice(self, payload: InvoiceCreate) -> Invoice:
        invoice_number = payload.invoice_number.strip().upper()

        if self.repository.get_by_number(invoice_number) is not None:
            raise DuplicateInvoiceError(invoice_number)

        invoice = Invoice(
            invoice_number=invoice_number,
            customer_name=payload.customer_name.strip(),
            customer_email=payload.customer_email,
            amount=Decimal(payload.amount),
            currency=payload.currency.upper(),
            status=payload.status,
            issued_at=payload.issued_at,
            notes=payload.notes,
        )
        return self.repository.create(invoice)

    def get_invoice(self, invoice_id: int) -> Invoice:
        invoice = self.repository.get_by_id(invoice_id)
        if invoice is None:
            raise InvoiceNotFoundError(invoice_id)
        return invoice

    def list_invoices(self, limit: int, offset: int) -> tuple[list[Invoice], int]:
        return self.repository.list(limit=limit, offset=offset), self.repository.count()
