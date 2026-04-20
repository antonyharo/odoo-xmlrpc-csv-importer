import csv
import threading
from pathlib import Path


class DlqWriter:
    """Responsável APENAS por gravar registros rejeitados com segurança em threads."""

    def __init__(self, file_path: Path | str) -> None:
        self.file_path = Path(file_path)
        self._lock = threading.Lock()

    def write_errors(self, batch: list, error_msg: str) -> None:
        if not batch:
            return

        try:
            with self._lock:
                file_exists = self.file_path.is_file()

                with open(
                    self.file_path, mode="a", newline="", encoding="utf-8"
                ) as file:
                    first_row = batch[0].copy()
                    fieldnames = list(first_row.keys()) + ["error_log"]

                    writer = csv.DictWriter(file, fieldnames=fieldnames)

                    if not file_exists:
                        writer.writeheader()

                    for row in batch:
                        row_copy = row.copy()
                        row_copy["error_log"] = error_msg
                        writer.writerow(row_copy)

        except Exception as e:
            raise RuntimeError(f"Failure to log in DLQ: {e}") from e
