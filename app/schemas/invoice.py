from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, condecimal

from app.models.invoice import InvoiceStatus

# `condecimal` already returns an Annotated type. Wrapping it in another
# `Annotated[Decimal, ...]` nests the metadata instead of merging it, and
# Pydantic v2 then silently ignores every constraint.
Amount = condecimal(gt=0, max_digits=12, decimal_places=2)


class InvoiceCreate(BaseModel):
    """Payload accepted when creating an invoice."""

    invoice_number: str = Field(min_length=1, max_length=50)
    customer_name: str = Field(min_length=1, max_length=120)
    customer_email: EmailStr
    amount: Amount
    currency: str = Field(default="USD", min_length=3, max_length=3)
    status: InvoiceStatus = InvoiceStatus.ISSUED
    issued_at: date
    notes: str | None = None


class InvoiceRead(BaseModel):
    """Invoice representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    customer_name: str
    customer_email: str
    amount: Decimal
    currency: str
    status: InvoiceStatus
    issued_at: date
    notes: str | None
    created_at: datetime


class InvoiceList(BaseModel):
    """Paginated collection of invoices."""

    items: list[InvoiceRead]
    total: int
    limit: int
    offset: int
