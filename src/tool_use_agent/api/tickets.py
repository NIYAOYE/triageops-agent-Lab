from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from tool_use_agent.api.ticket_models import (
    ApiErrorResponse,
    TicketCreateRequest,
    TicketDetailResponse,
    TicketPageResponse,
    TicketResponse,
)
from tool_use_agent.tickets.models import TicketPriority, TicketStatus
from tool_use_agent.tickets.repository import TicketAlreadyExists
from tool_use_agent.tickets.service import TicketService


def create_ticket_router(service: TicketService) -> APIRouter:
    router = APIRouter(prefix="/v1/tickets", tags=["tickets"])

    @router.post(
        "",
        response_model=TicketResponse,
        status_code=status.HTTP_201_CREATED,
        responses={status.HTTP_409_CONFLICT: {"model": ApiErrorResponse}},
    )
    def create_ticket(request: TicketCreateRequest):
        try:
            ticket = service.create_ticket(
                ticket_id=request.id,
                title=request.title,
                description=request.description,
                environment=request.environment,
                service=request.service,
                priority=request.priority,
                category=request.category,
            )
        except TicketAlreadyExists as exc:
            return _error_response(
                status.HTTP_409_CONFLICT,
                code=exc.code,
                message=str(exc),
                details={"ticket_id": exc.ticket_id},
            )
        return TicketResponse.model_validate(ticket)

    @router.get("", response_model=TicketPageResponse)
    def list_tickets(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
        status_filter: TicketStatus | None = Query(default=None, alias="status"),
        priority: TicketPriority | None = None,
        sort_by: Literal["created_at", "updated_at", "priority"] = "created_at",
        sort_order: Literal["asc", "desc"] = "desc",
    ) -> TicketPageResponse:
        result = service.list_tickets(
            page=page,
            page_size=page_size,
            status=status_filter,
            priority=priority,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return TicketPageResponse(
            items=[TicketResponse.model_validate(item) for item in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        )

    @router.get(
        "/{ticket_id}",
        response_model=TicketDetailResponse,
        responses={status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse}},
    )
    def get_ticket(ticket_id: str):
        try:
            detail = service.get_ticket_detail(ticket_id)
        except KeyError:
            return _error_response(
                status.HTTP_404_NOT_FOUND,
                code="ticket_not_found",
                message=f"Ticket {ticket_id} was not found.",
                details={"ticket_id": ticket_id},
            )
        return TicketDetailResponse.model_validate(detail)

    return router


def _error_response(
    status_code: int,
    *,
    code: str,
    message: str,
    details: dict[str, str],
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "request_id": str(uuid4()),
            "details": details,
        },
    )
