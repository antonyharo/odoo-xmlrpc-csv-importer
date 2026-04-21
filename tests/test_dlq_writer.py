import json
from pathlib import Path

import pytest

from src.odoo_xmlrpc_csv_importer.infrastructure.dlq_writer import (
    DlqWriter,
    JsonlDlqRecordSerializer,
    ThreadSafeJsonlFileSink,
)


def test_jsonl_serializer_includes_expected_fields(base_contact) -> None:
    serializer = JsonlDlqRecordSerializer()

    line = serializer.serialize(payload=base_contact, error_message="validation error")
    record = json.loads(line)

    assert set(record) == {"occurred_at", "error_message", "payload"}
    assert record["error_message"] == "validation error"
    assert record["payload"]["email"] == base_contact["email"]


def test_thread_safe_sink_appends_json_lines(tmp_path: Path) -> None:
    target = tmp_path / "dlq" / "failed_records.jsonl"
    sink = ThreadSafeJsonlFileSink(target)

    sink.write_lines(['{"foo":1}', '{"bar":2}\n'])

    content = target.read_text(encoding="utf-8").splitlines()
    assert content == ['{"foo":1}', '{"bar":2}']


def test_dlq_writer_persists_one_line_per_error(tmp_path: Path, base_contact) -> None:
    target = tmp_path / "failed_records.jsonl"
    writer = DlqWriter(file_path=target)

    second = base_contact | {"email": "other@example.com"}
    writer.write_errors([base_contact, second], "odoo timeout")

    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first_record = json.loads(lines[0])
    second_record = json.loads(lines[1])

    assert first_record["error_message"] == "odoo timeout"
    assert first_record["payload"]["email"] == base_contact["email"]
    assert second_record["payload"]["email"] == "other@example.com"


def test_dlq_writer_wraps_dependency_errors(base_contact) -> None:
    class BrokenSink:
        def write_lines(self, lines):  # noqa: ANN001
            list(lines)
            raise OSError("disk full")

    writer = DlqWriter(file_path="unused.jsonl", sink=BrokenSink())

    with pytest.raises(RuntimeError, match="Failed to persist DLQ records"):
        writer.write_errors([base_contact], "any error")
