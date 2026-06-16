import re
from pathlib import Path
from time import perf_counter
from typing import Any

from tool_use_agent.tools.contracts import ToolError, ToolResult
from tool_use_agent.tools.text_files import read_workspace_text_file


class LogScanTool:
    name = "log_scan"
    description = "Scan a workspace text log for keywords or a regular expression."
    args_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the configured workspace.",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Keywords to match in log lines.",
            },
            "pattern": {
                "type": "string",
                "description": "Optional regular expression to match log lines.",
            },
            "case_sensitive": {
                "type": "boolean",
                "default": False,
            },
            "context_lines": {
                "type": "integer",
                "minimum": 0,
                "maximum": 5,
                "default": 0,
            },
            "max_matches": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 20,
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

        keywords = [
            str(item)
            for item in arguments.get("keywords", [])
            if str(item).strip()
        ]
        pattern = str(arguments.get("pattern", "") or "").strip()
        if not keywords and not pattern:
            return self._error(
                "missing_scan_criteria",
                "Provide keywords or a regular expression pattern.",
                started_at,
            )

        case_sensitive = bool(arguments.get("case_sensitive", False))
        context_lines = self._bounded_int(arguments.get("context_lines", 0), 0, 5)
        max_matches = self._bounded_int(arguments.get("max_matches", 20), 1, 50)
        matcher = self._compile_pattern(pattern, case_sensitive, started_at)
        if isinstance(matcher, ToolResult):
            return matcher

        lines = loaded.content.splitlines()
        matches: list[dict[str, Any]] = []
        for index, line in enumerate(lines):
            matched_terms = self._matched_terms(
                line,
                keywords,
                matcher,
                case_sensitive,
            )
            if not matched_terms:
                continue
            start = max(0, index - context_lines)
            end = min(len(lines), index + context_lines + 1)
            matches.append(
                {
                    "line_number": index + 1,
                    "line": line,
                    "matched_terms": matched_terms,
                    "before": lines[start:index],
                    "after": lines[index + 1 : end],
                }
            )
            if len(matches) >= max_matches:
                break

        return ToolResult(
            success=True,
            data={
                "path": loaded.path,
                "scanned_lines": len(lines),
                "match_count": len(matches),
                "matches": matches,
            },
            metadata={
                "duration_ms": self._duration_ms(started_at),
                "encoding": loaded.encoding,
                "byte_count": loaded.byte_count,
                "truncated": len(matches) >= max_matches,
            },
        )

    @staticmethod
    def _bounded_int(value: Any, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = minimum
        return min(maximum, max(minimum, parsed))

    def _compile_pattern(
        self,
        pattern: str,
        case_sensitive: bool,
        started_at: float,
    ) -> re.Pattern[str] | None | ToolResult:
        if not pattern:
            return None
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            return re.compile(pattern, flags)
        except re.error:
            return self._error(
                "invalid_log_pattern",
                "Regular expression pattern is invalid.",
                started_at,
            )

    @staticmethod
    def _matched_terms(
        line: str,
        keywords: list[str],
        pattern: re.Pattern[str] | None,
        case_sensitive: bool,
    ) -> list[str]:
        haystack = line if case_sensitive else line.lower()
        terms = [
            keyword
            for keyword in keywords
            if (keyword if case_sensitive else keyword.lower()) in haystack
        ]
        if pattern is not None and pattern.search(line):
            terms.append("pattern")
        return terms

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
