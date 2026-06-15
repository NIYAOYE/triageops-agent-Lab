from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from tool_use_agent.investigations.models import (
    InvestigationStatus,
)
from tool_use_agent.tickets.models import (
    TicketPriority,
    TicketSource,
    TicketStatus,
)


class TicketCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1)
    environment: str = Field(min_length=1, max_length=100)
    service: str = Field(min_length=1, max_length=200)
    priority: TicketPriority
    category: str | None = Field(default=None, max_length=200)


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    environment: str
    service: str
    priority: TicketPriority
    category: str | None
    status: TicketStatus
    source: TicketSource
    created_at: datetime
    updated_at: datetime


class TicketPageResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    page: int
    page_size: int


class InvestigationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: InvestigationStatus
    started_at: datetime
    diagnosed_at: datetime | None
    completed_at: datetime | None
    stop_reason: str | None


class DiagnosisSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    suggested_priority: TicketPriority
    root_cause: str
    confidence: float
    evidence_ids: tuple[int, ...]
    recommended_actions: tuple[str, ...]
    reply_draft: str
    created_at: datetime


class TicketDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket: TicketResponse
    current_investigation: InvestigationSummaryResponse | None
    diagnosis_report: DiagnosisSummaryResponse | None


class ApiErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, str]
