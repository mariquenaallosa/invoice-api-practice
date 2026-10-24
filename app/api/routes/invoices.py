from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_invoice_service
from app.schemas.invoice import InvoiceCreate, InvoiceList, InvoiceRead
from app.services.invoice import InvoiceService

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=InvoiceRead)
def create_invoice(
    payload: InvoiceCreate,
    response: Response,
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> InvoiceRead:
    """Create an invoice."""
    invoice = service.create_invoice(payload)
    response.headers["Location"] = f"/invoices/{invoice.id}"
    return InvoiceRead.model_validate(invoice)


@router.get("", response_model=InvoiceList)
def list_invoices(
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InvoiceList:
    """List invoices with simple offset/limit pagination."""
    items, total = service.list_invoices(limit=limit, offset=offset)
    return InvoiceList(
        items=[InvoiceRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> InvoiceRead:
    """Fetch a single invoice by id."""
    invoice = service.get_invoice(invoice_id)
    return InvoiceRead.model_validate(invoice)
