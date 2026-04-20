import csv
from pathlib import Path
from typing import Dict, Generator


class CsvReader:
    def __init__(self, file_path: Path | str) -> None:
        self.file_path = Path(file_path)

    def stream(self) -> Generator[Dict[str, str], None, None]:
        try:
            with open(self.file_path, mode="r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                yield from reader
        except Exception as e:
            # Preserves original stacktrace
            raise RuntimeError(
                f"Error while streaming file {self.file_path}: {e}"
            ) from e
