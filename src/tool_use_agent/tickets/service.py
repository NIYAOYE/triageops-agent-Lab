from dataclasses import dataclass

from tool_use_agent.investigations.models import DiagnosisReport, Investigation
from tool_use_agent.tickets.models import (
    Ticket,
    TicketPriority,
    TicketSource,
    TicketStatus,
)
from tool_use_agent.tickets.repository import SQLiteTicketRepository


@dataclass(frozen=True)
class TicketPage:
    items: tuple[Ticket, ...]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class TicketDetail:
    ticket: Ticket
    current_investigation: Investigation | None
    diagnosis_report: DiagnosisReport | None


class TicketService:
    def __init__(self, repository: SQLiteTicketRepository):
        self._repository = repository

    def create_ticket(
        self,
        *,
        ticket_id: str,
        title: str,
        description: str,
        environment: str,
        service: str,
        priority: TicketPriority,
        category: str | None = None,
        source: TicketSource = TicketSource.MANUAL,
    ) -> Ticket:
        return self._repository.create_ticket(
            ticket_id=ticket_id,
            title=title,
            description=description,
            environment=environment,
            service=service,
            priority=priority,
            category=category,
            source=source,
        )

    def list_tickets(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> TicketPage:
        items, total = self._repository.list_tickets(
            offset=(page - 1) * page_size,
            limit=page_size,
            status=status,
            priority=priority,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return TicketPage(
            items=tuple(items),
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_ticket_detail(self, ticket_id: str) -> TicketDetail:
        ticket = self._repository.get_ticket(ticket_id)
        investigation = self._repository.get_current_investigation(ticket_id)
        report = (
            self._repository.get_diagnosis_report(investigation.id)
            if investigation is not None
            else None
        )
        return TicketDetail(
            ticket=ticket,
            current_investigation=investigation,
            diagnosis_report=report,
        )

    def close(self) -> None:
        self._repository.close()
