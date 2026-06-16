from dataclasses import dataclass
from pathlib import Path

from tool_use_agent.tools.contracts import ToolError, ToolResult


@dataclass(frozen=True)
class WorkspaceTextFile:
    path: str
    content: str
    byte_count: int
    encoding: str


def read_workspace_text_file(
    workspace_root: Path,
    raw_path: str,
    *,
    max_bytes: int,
) -> WorkspaceTextFile | ToolResult:
    path_value = str(raw_path or "").strip()
    requested_path = Path(path_value)
    root = workspace_root.resolve()

    if not path_value:
        return _error("invalid_file_path", "File path must not be empty.")
    if requested_path.is_absolute():
        return _error(
            "absolute_path_forbidden",
            "File path must be relative to the workspace.",
        )

    try:
        target = (root / requested_path).resolve(strict=False)
    except (OSError, RuntimeError):
        return _error("invalid_file_path", "File path could not be resolved.")

    if not target.is_relative_to(root):
        return _error(
            "path_outside_workspace",
            "File path resolves outside the workspace.",
        )

    try:
        target = target.resolve(strict=True)
    except FileNotFoundError:
        return _error("file_not_found", "The requested file does not exist.")
    except (OSError, RuntimeError):
        return _error(
            "file_read_error",
            "The requested file could not be accessed.",
        )

    if not target.is_relative_to(root):
        return _error(
            "path_outside_workspace",
            "File path resolves outside the workspace.",
        )
    if not target.is_file():
        return _error("not_a_file", "The requested path is not a regular file.")

    try:
        byte_count = target.stat().st_size
        if byte_count > max_bytes:
            return _error(
                "file_too_large",
                f"File exceeds the {max_bytes}-byte limit.",
            )
        content_bytes = target.read_bytes()
    except OSError:
        return _error("file_read_error", "The requested file could not be read.")

    if b"\x00" in content_bytes:
        return _error("binary_file_forbidden", "Binary files are not supported.")

    decoded = _decode_text(content_bytes)
    if decoded is None:
        return _error(
            "unsupported_text_encoding",
            "File is not valid UTF-8 or GB18030 text.",
        )
    content, encoding = decoded
    return WorkspaceTextFile(
        path=target.relative_to(root).as_posix(),
        content=content,
        byte_count=byte_count,
        encoding=encoding,
    )


def _decode_text(content: bytes) -> tuple[str, str] | None:
    if content.startswith(b"\xef\xbb\xbf"):
        return content.decode("utf-8-sig"), "utf-8-sig"
    try:
        return content.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        try:
            return content.decode("gb18030"), "gb18030"
        except UnicodeDecodeError:
            return None


def _error(code: str, message: str) -> ToolResult:
    return ToolResult(success=False, error=ToolError(code=code, message=message))
