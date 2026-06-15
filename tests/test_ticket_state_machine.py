import pytest

from tool_use_agent.tickets.models import TicketStatus
from tool_use_agent.tickets.state_machine import (
    InvalidTicketTransition,
    transition_ticket_status,
)


ALLOWED_TRANSITIONS = {
    (TicketStatus.NEW, TicketStatus.QUEUED),
    (TicketStatus.QUEUED, TicketStatus.INVESTIGATING),
    (TicketStatus.INVESTIGATING, TicketStatus.AWAITING_REVIEW),
    (TicketStatus.INVESTIGATING, TicketStatus.FAILED),
    (TicketStatus.FAILED, TicketStatus.INVESTIGATING),
    (TicketStatus.AWAITING_REVIEW, TicketStatus.APPROVED),
    (TicketStatus.AWAITING_REVIEW, TicketStatus.INVESTIGATING),
}


@pytest.mark.parametrize(
    ("current", "target"),
    sorted(ALLOWED_TRANSITIONS, key=lambda pair: (pair[0].value, pair[1].value)),
)
def test_defined_ticket_status_transitions_are_allowed(current, target):
    assert transition_ticket_status(current, target) is target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (current, target)
        for current in TicketStatus
        for target in TicketStatus
        if (current, target) not in ALLOWED_TRANSITIONS
    ],
)
def test_undefined_ticket_status_transitions_raise_stable_domain_error(
    current,
    target,
):
    with pytest.raises(InvalidTicketTransition) as exc_info:
        transition_ticket_status(current, target)

    assert exc_info.value.code == "invalid_ticket_status_transition"
    assert exc_info.value.current is current
    assert exc_info.value.target is target
