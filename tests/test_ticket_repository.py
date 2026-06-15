import pytest

from tool_use_agent.tickets.models import (
    TicketPriority,
    TicketSource,
    TicketStatus,
)
from tool_use_agent.tickets.repository import (
    SQLiteTicketRepository,
    TicketAlreadyExists,
)
from tool_use_agent.tickets.state_machine import InvalidTicketTransition


def test_ticket_survives_repository_restart(tmp_path):
    path = tmp_path / "agent.db"
    first = SQLiteTicketRepository(path)
    created = first.create_ticket(
        ticket_id="INC-1042",
        title="Database connection timeouts",
        description="API requests fail while acquiring a connection.",
        environment="production",
        service="orders-api",
        priority=TicketPriority.P1,
        category="runtime/database",
        source=TicketSource.MANUAL,
    )
    first.close()

    second = SQLiteTicketRepository(path)
    try:
        restored = second.get_ticket("INC-1042")

        assert restored == created
        assert restored.status is TicketStatus.NEW
        assert restored.created_at.tzinfo is not None
        assert restored.updated_at == restored.created_at
    finally:
        second.close()


def test_duplicate_ticket_id_raises_stable_domain_error(tmp_path):
    repo = SQLiteTicketRepository(tmp_path / "agent.db")
    try:
        values = {
            "ticket_id": "INC-1042",
            "title": "Database connection timeouts",
            "description": "Requests fail.",
            "environment": "production",
            "service": "orders-api",
            "priority": TicketPriority.P1,
        }
        repo.create_ticket(**values)

        with pytest.raises(TicketAlreadyExists) as exc_info:
            repo.create_ticket(**values)

        assert exc_info.value.code == "ticket_already_exists"
        assert exc_info.value.ticket_id == "INC-1042"
    finally:
        repo.close()


def test_legal_status_transition_is_persisted(tmp_path):
    path = tmp_path / "agent.db"
    repo = SQLiteTicketRepository(path)
    try:
        created = repo.create_ticket(
            ticket_id="INC-1042",
            title="Database connection timeouts",
            description="Requests fail.",
            environment="production",
            service="orders-api",
            priority=TicketPriority.P1,
        )

        queued = repo.transition_status(created.id, TicketStatus.QUEUED)

        assert queued.status is TicketStatus.QUEUED
        assert queued.updated_at >= created.updated_at
        assert repo.get_ticket(created.id) == queued
    finally:
        repo.close()


def test_illegal_status_transition_does_not_change_persisted_ticket(tmp_path):
    repo = SQLiteTicketRepository(tmp_path / "agent.db")
    try:
        created = repo.create_ticket(
            ticket_id="INC-1042",
            title="Database connection timeouts",
            description="Requests fail.",
            environment="production",
            service="orders-api",
            priority=TicketPriority.P1,
        )

        with pytest.raises(InvalidTicketTransition):
            repo.transition_status(created.id, TicketStatus.APPROVED)

        assert repo.get_ticket(created.id) == created
    finally:
        repo.close()
