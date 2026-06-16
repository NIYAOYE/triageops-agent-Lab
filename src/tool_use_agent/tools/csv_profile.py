from collections import Counter
import csv
from io import StringIO
from pathlib import Path
from time import perf_counter
from typing import Any

from tool_use_agent.tools.contracts import ToolError, ToolResult
from tool_use_agent.tools.text_files import read_workspace_text_file


class CsvProfileTool:
    name = "csv_profile"
    description = "Profile a workspace CSV file with row, column, empty, duplicate, and value counts."
    args_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the configured workspace.",
            },
            "group_by": {
                "type": "string",
                "description": "Optional column name to count values for.",
            },
            "max_sample_rows": {
                "type": "integer",
                "minimum": 0,
                "maximum": 10,
                "default": 3,
            },
        },
        "required": ["path"],
    }

    def __init__(self, workspace_root: Path, *, max_bytes: int = 1_000_000):
        self._workspace_root = workspace_root
        self._max_bytes = max(1, int(max_bytes))

    def invoke(self, arguments: dict[str, Any]) -> ToolResult:
        started_at = perf_counter()
        loaded = read_workspace_text_file(
            self._workspace_root,
            str(arguments.get("path", "")),
            max_bytes=self._max_bytes,
        )
        if isinstance(loaded, ToolResult):
            return self._with_duration(loaded, started_at)

        reader = csv.DictReader(StringIO(loaded.content))
        if reader.fieldnames is None:
            return self._error(
                "csv_header_required",
                "CSV header is required.",
                started_at,
            )
        columns = [name.strip() for name in reader.fieldnames]
        rows = [
            {column: str(row.get(column, "") or "") for column in columns}
            for row in reader
        ]
        group_by = str(arguments.get("group_by", "") or "").strip()
        if group_by and group_by not in columns:
            return self._error(
                "csv_column_not_found",
                "The requested group_by column does not exist.",
                started_at,
            )
        max_sample_rows = self._bounded_int(
            arguments.get("max_sample_rows", 3),
            0,
            10,
        )

        value_counts = (
            dict(Counter(row[group_by] for row in rows))
            if group_by
            else None
        )
        data: dict[str, Any] = {
            "path": loaded.path,
            "row_count": len(rows),
            "columns": columns,
            "empty_counts": {
                column: sum(1 for row in rows if row[column] == "")
                for column in columns
            },
            "duplicate_counts": {
                column: self._duplicate_count(row[column] for row in rows)
                for column in columns
            },
            "sample_rows": rows[:max_sample_rows],
        }
        if value_counts is not None:
            data["value_counts"] = value_counts

        return ToolResult(
            success=True,
            data=data,
            metadata={
                "duration_ms": self._duration_ms(started_at),
                "encoding": loaded.encoding,
                "byte_count": loaded.byte_count,
            },
        )

    @staticmethod
    def _duplicate_count(values: Any) -> int:
        counts = Counter(values)
        return sum(count - 1 for count in counts.values() if count > 1)

    @staticmethod
    def _bounded_int(value: Any, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = minimum
        return min(maximum, max(minimum, parsed))

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((perf_counter() - started_at) * 1000)

    def _with_duration(self, result: ToolResult, started_at: float) -> ToolResult:
        return ToolResult(
            success=result.success,
            data=result.data,
            error=result.error,
            metadata={**result.metadata, "duration_ms": self._duration_ms(started_at)},
        )

    def _error(self, code: str, message: str, started_at: float) -> ToolResult:
        return ToolResult(
            success=False,
            error=ToolError(code=code, message=message),
            metadata={"duration_ms": self._duration_ms(started_at)},
        )
