from tool_use_agent.memory.repository import SQLiteRepository
from tool_use_agent.tickets.models import TicketPriority, TicketStatus
from tool_use_agent.tickets.repository import SQLiteTicketRepository
from tool_use_agent.tickets.service import TicketService


def create_ticket(service, ticket_id, priority=TicketPriority.P2):
    return service.create_ticket(
        ticket_id=ticket_id,
        title=f"Ticket {ticket_id}",
        description="Requests fail.",
        environment="production",
        service="orders-api",
        priority=priority,
    )


def test_ticket_service_lists_filtered_paginated_tickets(tmp_path):
    repository = SQLiteTicketRepository(tmp_path / "agent.db")
    service = TicketService(repository)
    try:
        first = create_ticket(service, "INC-1001", TicketPriority.P1)
        second = create_ticket(service, "INC-1002", TicketPriority.P1)
        create_ticket(service, "INC-1003", TicketPriority.P2)
        repository.transition_status(first.id, TicketStatus.QUEUED)
        repository.transition_status(second.id, TicketStatus.QUEUED)

        page = service.list_tickets(
            page=2,
            page_size=1,
            status=TicketStatus.QUEUED,
            priority=TicketPriority.P1,
            sort_by="created_at",
            sort_order="asc",
        )

        assert page.total == 2
        assert page.page == 2
        assert page.page_size == 1
        assert [item.id for item in page.items] == ["INC-1002"]
    finally:
        repository.close()


def test_ticket_service_detail_includes_current_investigation_and_report(tmp_path):
    path = tmp_path / "agent.db"
    memory = SQLiteRepository(path)
    memory.create_session("session-1")
    repository = SQLiteTicketRepository(path)
    service = TicketService(repository)
    try:
        ticket = create_ticket(service, "INC-1001", TicketPriority.P1)
        investigation = repository.create_investigation(ticket.id, "session-1")

        detail = service.get_ticket_detail(ticket.id)

        assert detail.ticket == ticket
        assert detail.current_investigation == investigation
        assert detail.diagnosis_report is None
    finally:
        repository.close()
        memory.close()
