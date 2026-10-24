from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.repositories.invoice import InvoiceRepository

VALID_PAYLOAD = {
    "invoice_number": "INV-001",
    "customer_name": "Ada Lovelace",
    "customer_email": "ada@example.com",
    "amount": "1250.50",
    "currency": "USD",
    "issued_at": "2026-01-15",
}


def test_create_invoice_returns_201(client: TestClient) -> None:
    response = client.post("/invoices", json=VALID_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["invoice_number"] == "INV-001"
    assert body["amount"] == "1250.50"
    assert body["status"] == "issued"
    assert response.headers["location"].endswith(f"/invoices/{body['id']}")


def test_create_invoice_returns_409_on_duplicate(client: TestClient) -> None:
    client.post("/invoices", json=VALID_PAYLOAD)

    response = client.post("/invoices", json=VALID_PAYLOAD)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invoice_duplicate"


def test_create_invoice_returns_409_on_duplicate_ignoring_case_and_spaces(
    client: TestClient,
) -> None:
    client.post("/invoices", json=VALID_PAYLOAD)

    response = client.post("/invoices", json={**VALID_PAYLOAD, "invoice_number": " inv-001 "})

    assert response.status_code == 409


def test_create_invoice_returns_422_on_invalid_payload(client: TestClient) -> None:
    response = client.post("/invoices", json={**VALID_PAYLOAD, "amount": "not-a-number"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_invoice_returns_422_on_amount_with_three_decimals(client: TestClient) -> None:
    response = client.post("/invoices", json={**VALID_PAYLOAD, "amount": "10.999"})

    assert response.status_code == 422


def test_create_invoice_returns_422_on_invalid_status(client: TestClient) -> None:
    response = client.post("/invoices", json={**VALID_PAYLOAD, "status": "cancelled"})

    assert response.status_code == 422


def test_create_invoice_ignores_unknown_fields(client: TestClient) -> None:
    response = client.post("/invoices", json={**VALID_PAYLOAD, "total": 99})

    assert response.status_code == 201


def test_get_invoice_returns_200(client: TestClient) -> None:
    created = client.post("/invoices", json=VALID_PAYLOAD).json()

    response = client.get(f"/invoices/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_invoice_returns_404_when_not_found(client: TestClient) -> None:
    response = client.get("/invoices/999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "invoice_not_found"


def test_list_invoices_returns_paginated_items(client: TestClient) -> None:
    for index in range(3):
        client.post("/invoices", json={**VALID_PAYLOAD, "invoice_number": f"INV-{index:03d}"})

    response = client.get("/invoices", params={"limit": 2, "offset": 0})

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0


def test_list_invoices_returns_422_on_invalid_limit(client: TestClient) -> None:
    assert client.get("/invoices", params={"limit": 0}).status_code == 422
    assert client.get("/invoices", params={"limit": 101}).status_code == 422
    assert client.get("/invoices", params={"limit": "abc"}).status_code == 422


def test_list_invoices_returns_422_on_negative_offset(client: TestClient) -> None:
    assert client.get("/invoices", params={"offset": -1}).status_code == 422


def test_unexpected_error_returns_500_without_leaking_details(
    client_raising: TestClient, monkeypatch
) -> None:
    def boom(self, invoice_id: int) -> None:
        raise RuntimeError("boom-secret")

    monkeypatch.setattr("app.services.invoice.InvoiceService.get_invoice", boom)

    response = client_raising.get("/invoices/1")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "boom-secret" not in response.text


def test_invoices_created_by_previous_tests_are_rolled_back(client: TestClient) -> None:
    response = client.post("/invoices", json=VALID_PAYLOAD)

    assert response.status_code == 201

    listing = client.get("/invoices", params={"limit": 100})

    assert listing.json()["total"] == 1


def build_invoice(invoice_number: str) -> Invoice:
    return Invoice(
        invoice_number=invoice_number,
        customer_name="Ada Lovelace",
        customer_email="ada@example.com",
        amount=Decimal("1250.50"),
        currency="USD",
        status=InvoiceStatus.ISSUED,
        issued_at=date(2026, 1, 15),
    )


def test_unique_constraint_is_enforced_by_the_database(db_session: Session) -> None:
    """The database rejects the duplicate and the repository rolls the session back."""
    repository = InvoiceRepository(db_session)
    repository.create(build_invoice("INV-DUP"))

    with pytest.raises(IntegrityError):
        repository.create(build_invoice("INV-DUP"))

    # The failed transaction was rolled back, so the session is still usable.
    assert repository.count() == 1


def test_create_invoice_returns_409_when_the_database_rejects_the_insert(
    client: TestClient, monkeypatch
) -> None:
    """The service pre-check is not the only guard: the unique constraint is the real one."""

    def raise_integrity_error(self, invoice: Invoice) -> Invoice:
        raise IntegrityError("INSERT", {}, Exception("duplicate key value violates unique"))

    monkeypatch.setattr(InvoiceRepository, "create", raise_integrity_error)

    response = client.post("/invoices", json=VALID_PAYLOAD)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invoice_duplicate"
