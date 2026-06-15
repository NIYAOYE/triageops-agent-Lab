import pytest

from tests.fakes import FakeAgentRunner, FakeSummarizer
from tool_use_agent.api.app import create_app
from tool_use_agent.memory.repository import SQLiteRepository
from tool_use_agent.service import ChatService
from tool_use_agent.tickets.repository import SQLiteTicketRepository
from tool_use_agent.tickets.service import TicketService


@pytest.fixture
def app(tmp_path):
    database_path = tmp_path / "agent.db"
    repository = SQLiteRepository(database_path)
    ticket_repository = SQLiteTicketRepository(database_path)
    runner = FakeAgentRunner(
        answer="final answer",
        events=[
            {
                "event": "tool_start",
                "call_id": "call-api",
                "tool": "web_search",
                "arguments": {"query": "q"},
            },
            {
                "event": "tool_result",
                "call_id": "call-api",
                "tool": "web_search",
                "result": {"success": True, "data": []},
            },
        ],
    )
    service = ChatService(
        repository=repository,
        runner=runner,
        summarizer=FakeSummarizer(),
        context_char_threshold=40_000,
        recent_message_count=12,
    )
    ticket_service = TicketService(ticket_repository)
    application = create_app(service, ticket_service)
    yield application
    ticket_repository.close()
    repository.close()
