from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.invoice import InvoiceRepository
from app.services.invoice import InvoiceService


def get_invoice_service(session: Session = Depends(get_db)) -> InvoiceService:  # noqa: B008
    """Build the invoice service for a request."""
    return InvoiceService(InvoiceRepository(session))
