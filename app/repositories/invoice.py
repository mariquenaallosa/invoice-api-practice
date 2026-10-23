from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.invoice import Invoice


class InvoiceRepository:
    """All database access for invoices lives here."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, invoice: Invoice) -> Invoice:
        self.session.add(invoice)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        self.session.refresh(invoice)
        return invoice

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        return self.session.get(Invoice, invoice_id)

    def get_by_number(self, invoice_number: str) -> Invoice | None:
        statement = select(Invoice).where(Invoice.invoice_number == invoice_number)
        return self.session.execute(statement).scalar_one_or_none()

    def list(self, limit: int, offset: int) -> list[Invoice]:
        statement = select(Invoice).order_by(Invoice.id).limit(limit).offset(offset)
        return list(self.session.execute(statement).scalars().all())

    def count(self) -> int:
        statement = select(func.count()).select_from(Invoice)
        return int(self.session.execute(statement).scalar_one())
