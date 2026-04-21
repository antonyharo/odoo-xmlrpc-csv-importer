import json
import threading
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class DlqRecordSerializer(Protocol):
    def serialize(self, payload: Mapping[str, Any], error_message: str) -> str: ...


class DlqLineSink(Protocol):
    def write_lines(self, lines: Iterable[str]) -> None: ...


class JsonlDlqRecordSerializer:
    """Serializes a DLQ record as one JSON line."""

    def serialize(self, payload: Mapping[str, Any], error_message: str) -> str:
        dlq_record = {
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "error_message": error_message,
            "payload": dict(payload),
        }
        return json.dumps(dlq_record, default=str, ensure_ascii=False)


class ThreadSafeJsonlFileSink:
    """Appends JSON lines to file safely in multithread usage."""

    def __init__(self, file_path: Path | str) -> None:
        self._file_path = Path(file_path)
        self._lock = threading.Lock()

    def write_lines(self, lines: Iterable[str]) -> None:
        buffered_lines = list(lines)
        if not buffered_lines:
            return

        with self._lock:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with self._file_path.open(mode="a", encoding="utf-8", newline="\n") as file:
                for line in buffered_lines:
                    file.write(line.rstrip("\n"))
                    file.write("\n")


class DlqWriter:
    """Coordinates DLQ serialization and persistence."""

    def __init__(
        self,
        file_path: Path | str,
        serializer: DlqRecordSerializer | None = None,
        sink: DlqLineSink | None = None,
    ) -> None:
        self._serializer = serializer or JsonlDlqRecordSerializer()
        self._sink = sink or ThreadSafeJsonlFileSink(file_path)

    def write_errors(self, batch: list[dict[str, Any]], error_message: str) -> None:
        if not batch:
            return

        try:
            lines = (
                self._serializer.serialize(payload=row, error_message=error_message)
                for row in batch
            )
            self._sink.write_lines(lines)
        except Exception as exc:
            raise RuntimeError(f"Failed to persist DLQ records: {exc}") from exc
