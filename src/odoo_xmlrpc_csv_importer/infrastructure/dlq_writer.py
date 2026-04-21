import json
import traceback
import threading
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class DlqRecordSerializer(Protocol):
    def serialize(
        self,
        payload: Mapping[str, Any],
        error_category: str,
        error_details: Mapping[str, Any] | None = None,
    ) -> str: ...


class DlqLineSink(Protocol):
    def write_lines(self, lines: Iterable[str]) -> None: ...


class JsonlDlqRecordSerializer:
    """Serializes a DLQ record as one JSON line."""

    def serialize(
        self,
        payload: Mapping[str, Any],
        error_category: str,
        error_details: Mapping[str, Any] | None = None,
    ) -> str:
        dlq_record = {
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "error_message": error_category,
            "error_category": error_category,
            "error_details": dict(error_details) if error_details else None,
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

    def write_errors(
        self,
        batch: list[dict[str, Any]],
        error_category: str,
        *,
        exception: Exception | None = None,
        error_details: Mapping[str, Any] | None = None,
    ) -> None:
        if not batch:
            return

        try:
            normalized_details = self._build_error_details(
                error_category=error_category,
                exception=exception,
                explicit_details=error_details,
            )
            lines = (
                self._serializer.serialize(
                    payload=row,
                    error_category=error_category,
                    error_details=normalized_details,
                )
                for row in batch
            )
            self._sink.write_lines(lines)
        except Exception as exc:
            raise RuntimeError(f"Failed to persist DLQ records: {exc}") from exc

    @staticmethod
    def _build_error_details(
        *,
        error_category: str,
        exception: Exception | None,
        explicit_details: Mapping[str, Any] | None,
    ) -> Mapping[str, Any]:
        if explicit_details:
            return explicit_details

        if exception:
            return {
                "error_type": type(exception).__name__,
                "message": str(exception),
                "traceback": "".join(
                    traceback.format_exception(
                        type(exception), exception, exception.__traceback__
                    )
                ),
            }

        return {"error_type": "UnknownError", "message": error_category, "traceback": None}
