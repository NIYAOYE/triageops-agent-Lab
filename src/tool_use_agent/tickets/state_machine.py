from tool_use_agent.tickets.models import TicketStatus


_ALLOWED_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.NEW: frozenset({TicketStatus.QUEUED}),
    TicketStatus.QUEUED: frozenset({TicketStatus.INVESTIGATING}),
    TicketStatus.INVESTIGATING: frozenset(
        {TicketStatus.AWAITING_REVIEW, TicketStatus.FAILED}
    ),
    TicketStatus.AWAITING_REVIEW: frozenset(
        {TicketStatus.APPROVED, TicketStatus.INVESTIGATING}
    ),
    TicketStatus.FAILED: frozenset({TicketStatus.INVESTIGATING}),
    TicketStatus.APPROVED: frozenset(),
}


class InvalidTicketTransition(ValueError):
    code = "invalid_ticket_status_transition"

    def __init__(self, current: TicketStatus, target: TicketStatus):
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition ticket from {current} to {target}.")


def transition_ticket_status(
    current: TicketStatus,
    target: TicketStatus,
) -> TicketStatus:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidTicketTransition(current, target)
    return target
