import json
import re
from pathlib import Path
from time import perf_counter
from typing import Any

from tool_use_agent.tools.contracts import ToolError, ToolResult
from tool_use_agent.tools.text_files import read_workspace_text_file


_SEGMENT_PATTERN = re.compile(r"([^\[\].]+)|\[(\d+)\]")


class JsonQueryTool:
    name = "json_query"
    description = "Read a workspace JSON file and return a simple dotted path value."
    args_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the configured workspace.",
            },
            "query": {
                "type": "string",
                "description": "Dotted JSON path, for example errors[0].code.",
            },
        },
        "required": ["path", "query"],
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

        query = str(arguments.get("query", "") or "").strip()
        if not query:
            return self._error(
                "invalid_json_query",
                "JSON query must not be empty.",
                started_at,
            )

        try:
            document = json.loads(loaded.content)
        except json.JSONDecodeError:
            return self._error(
                "invalid_json",
                "The requested file is not valid JSON.",
                started_at,
            )

        try:
            value = self._resolve(document, query)
        except (KeyError, IndexError, TypeError, ValueError):
            return self._error(
                "json_query_not_found",
                "JSON query did not match a value.",
                started_at,
            )

        return ToolResult(
            success=True,
            data={
                "path": loaded.path,
                "query": query,
                "value": value,
                "value_type": type(value).__name__,
            },
            metadata={
                "duration_ms": self._duration_ms(started_at),
                "encoding": loaded.encoding,
                "byte_count": loaded.byte_count,
            },
        )

    @classmethod
    def _resolve(cls, document: Any, query: str) -> Any:
        current = document
        for part in query.split("."):
            if not part:
                raise ValueError("empty query segment")
            position = 0
            for match in _SEGMENT_PATTERN.finditer(part):
                if match.start() != position:
                    raise ValueError("invalid query segment")
                key, index = match.groups()
                if key is not None:
                    if not isinstance(current, dict):
                        raise TypeError("current value is not an object")
                    current = current[key]
                else:
                    if not isinstance(current, list):
                        raise TypeError("current value is not an array")
                    current = current[int(index)]
                position = match.end()
            if position != len(part):
                raise ValueError("invalid query segment")
        return current

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
