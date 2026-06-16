import csv
import json

from tool_use_agent.tools.csv_profile import CsvProfileTool
from tool_use_agent.tools.json_query import JsonQueryTool
from tool_use_agent.tools.log_scan import LogScanTool


def test_log_scan_returns_matches_with_context(tmp_path):
    (tmp_path / "app.log").write_text(
        "\n".join(
            [
                "2026-06-16T10:00:00Z INFO boot complete",
                "2026-06-16T10:01:00Z ERROR database timeout",
                "2026-06-16T10:02:00Z INFO retry scheduled",
                "2026-06-16T10:03:00Z WARN connection pool high",
            ]
        ),
        encoding="utf-8",
    )

    result = LogScanTool(tmp_path).invoke(
        {
            "path": "app.log",
            "keywords": ["error", "WARN"],
            "context_lines": 1,
            "max_matches": 10,
        }
    )

    assert result.success is True
    assert result.data["path"] == "app.log"
    assert result.data["scanned_lines"] == 4
    assert result.data["match_count"] == 2
    assert result.data["matches"][0] == {
        "line_number": 2,
        "line": "2026-06-16T10:01:00Z ERROR database timeout",
        "matched_terms": ["error"],
        "before": ["2026-06-16T10:00:00Z INFO boot complete"],
        "after": ["2026-06-16T10:02:00Z INFO retry scheduled"],
    }
    assert result.metadata["truncated"] is False


def test_log_scan_rejects_paths_outside_workspace(tmp_path):
    result = LogScanTool(tmp_path).invoke({"path": "../secret.log"})

    assert result.success is False
    assert result.error.code == "path_outside_workspace"


def test_json_query_reads_nested_value(tmp_path):
    (tmp_path / "incident.json").write_text(
        json.dumps(
            {
                "errors": [{"code": "E42", "count": 2}],
                "meta": {"service": "orders-api"},
            }
        ),
        encoding="utf-8",
    )

    result = JsonQueryTool(tmp_path).invoke(
        {"path": "incident.json", "query": "errors[0].code"}
    )

    assert result.success is True
    assert result.data == {
        "path": "incident.json",
        "query": "errors[0].code",
        "value": "E42",
        "value_type": "str",
    }


def test_json_query_reports_missing_path_without_throwing(tmp_path):
    (tmp_path / "incident.json").write_text(
        json.dumps({"errors": []}),
        encoding="utf-8",
    )

    result = JsonQueryTool(tmp_path).invoke(
        {"path": "incident.json", "query": "errors[0].code"}
    )

    assert result.success is False
    assert result.error.code == "json_query_not_found"


def test_csv_profile_summarizes_columns_and_value_counts(tmp_path):
    with (tmp_path / "tickets.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "priority", "service", "owner"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {"id": "INC-1", "priority": "P1", "service": "orders", "owner": ""},
                {"id": "INC-2", "priority": "P1", "service": "orders", "owner": "li"},
                {"id": "INC-3", "priority": "P2", "service": "billing", "owner": ""},
            ]
        )

    result = CsvProfileTool(tmp_path).invoke(
        {
            "path": "tickets.csv",
            "group_by": "priority",
            "max_sample_rows": 2,
        }
    )

    assert result.success is True
    assert result.data["path"] == "tickets.csv"
    assert result.data["row_count"] == 3
    assert result.data["columns"] == ["id", "priority", "service", "owner"]
    assert result.data["empty_counts"] == {"id": 0, "priority": 0, "service": 0, "owner": 2}
    assert result.data["duplicate_counts"] == {"id": 0, "priority": 1, "service": 1, "owner": 1}
    assert result.data["value_counts"] == {"P1": 2, "P2": 1}
    assert result.data["sample_rows"] == [
        {"id": "INC-1", "priority": "P1", "service": "orders", "owner": ""},
        {"id": "INC-2", "priority": "P1", "service": "orders", "owner": "li"},
    ]


def test_csv_profile_rejects_missing_group_column(tmp_path):
    (tmp_path / "tickets.csv").write_text("id,priority\nINC-1,P1\n", encoding="utf-8")

    result = CsvProfileTool(tmp_path).invoke(
        {"path": "tickets.csv", "group_by": "service"}
    )

    assert result.success is False
    assert result.error.code == "csv_column_not_found"
