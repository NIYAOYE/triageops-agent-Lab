from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from threading import RLock

from tool_use_agent.tickets.models import (
    Ticket,
    TicketPriority,
    TicketSource,
    TicketStatus,
)
from tool_use_agent.tickets.state_machine import transition_ticket_status


class TicketAlreadyExists(ValueError):
    code = "ticket_already_exists"

    def __init__(self, ticket_id: str):
        self.ticket_id = ticket_id
        super().__init__(f"Ticket {ticket_id} already exists.")


class SQLiteTicketRepository:
    def __init__(self, database_path: Path):
        self._database_path = Path(database_path).resolve()
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(
            self._database_path,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._migrate()

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
        now = self._utc_now()
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    """
                    INSERT INTO tickets (
                        id,
                        title,
                        description,
                        environment,
                        service,
                        priority,
                        category,
                        status,
                        source,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ticket_id,
                        title,
                        description,
                        environment,
                        service,
                        priority.value,
                        category,
                        TicketStatus.NEW.value,
                        source.value,
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise TicketAlreadyExists(ticket_id) from exc
        return self.get_ticket(ticket_id)

    def get_ticket(self, ticket_id: str) -> Ticket:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT
                    id,
                    title,
                    description,
                    environment,
                    service,
                    priority,
                    category,
                    status,
                    source,
                    created_at,
                    updated_at
                FROM tickets
                WHERE id = ?
                """,
                (ticket_id,),
            ).fetchone()
        if row is None:
            raise KeyError("ticket_not_found")
        return self._ticket_from_row(row)

    def transition_status(
        self,
        ticket_id: str,
        target: TicketStatus,
    ) -> Ticket:
        with self._lock, self._connection:
            current = self.get_ticket(ticket_id)
            status = transition_ticket_status(current.status, target)
            self._connection.execute(
                """
                UPDATE tickets
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status.value, self._utc_now(), ticket_id),
            )
        return self.get_ticket(ticket_id)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _migrate(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    service TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    category TEXT,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_tickets_status_priority
                    ON tickets(status, priority, created_at);
                """
            )

    @staticmethod
    def _ticket_from_row(row: sqlite3.Row) -> Ticket:
        return Ticket(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            environment=row["environment"],
            service=row["service"],
            priority=TicketPriority(row["priority"]),
            category=row["category"],
            status=TicketStatus(row["status"]),
            source=TicketSource(row["source"]),
            created_at=SQLiteTicketRepository._parse_datetime(row["created_at"]),
            updated_at=SQLiteTicketRepository._parse_datetime(row["updated_at"]),
        )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        return datetime.fromisoformat(value)
