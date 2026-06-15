from fastapi.testclient import TestClient


def ticket_payload(ticket_id="INC-1042", priority="P1"):
    return {
        "id": ticket_id,
        "title": "Database connection timeouts",
        "description": "Requests fail while acquiring a connection.",
        "environment": "production",
        "service": "orders-api",
        "priority": priority,
        "category": "runtime/database",
    }


def test_create_list_and_get_ticket(app):
    client = TestClient(app)

    created = client.post("/v1/tickets", json=ticket_payload())
    listed = client.get(
        "/v1/tickets",
        params={
            "page": 1,
            "page_size": 10,
            "priority": "P1",
            "status": "NEW",
            "sort_by": "created_at",
            "sort_order": "asc",
        },
    )
    detail = client.get("/v1/tickets/INC-1042")

    assert created.status_code == 201
    assert created.json()["id"] == "INC-1042"
    assert created.json()["source"] == "manual"
    assert created.json()["status"] == "NEW"
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["page"] == 1
    assert [item["id"] for item in listed.json()["items"]] == ["INC-1042"]
    assert detail.status_code == 200
    assert detail.json()["ticket"]["id"] == "INC-1042"
    assert detail.json()["current_investigation"] is None
    assert detail.json()["diagnosis_report"] is None


def test_duplicate_ticket_returns_stable_conflict_error(app):
    client = TestClient(app)
    client.post("/v1/tickets", json=ticket_payload())

    response = client.post("/v1/tickets", json=ticket_payload())

    assert response.status_code == 409
    assert response.json()["code"] == "ticket_already_exists"
    assert response.json()["message"] == "Ticket INC-1042 already exists."
    assert response.json()["request_id"]
    assert response.json()["details"] == {"ticket_id": "INC-1042"}


def test_missing_ticket_returns_stable_not_found_error(app):
    response = TestClient(app).get("/v1/tickets/INC-missing")

    assert response.status_code == 404
    assert response.json()["code"] == "ticket_not_found"
    assert response.json()["message"] == "Ticket INC-missing was not found."
    assert response.json()["request_id"]
    assert response.json()["details"] == {"ticket_id": "INC-missing"}


def test_ticket_request_validation_uses_422(app):
    payload = ticket_payload()
    payload["title"] = ""

    response = TestClient(app).post("/v1/tickets", json=payload)

    assert response.status_code == 422
