import csv
import os
import threading
from pathlib import Path
from typing import Generator

from pydantic import ValidationError

from odoo_xmlrpc_csv_importer.domain.contact import is_duplicate, validate_contact
from odoo_xmlrpc_csv_importer.infrastructure.import_stats import ImportStats


class CsvManager:
    def __init__(
        self,
        contacts_file: Path,
        dlq_file: str,
        import_stats: ImportStats | None = None,
    ) -> None:
        self.contacts_file = contacts_file
        self.dlq_file = dlq_file
        self.import_stats = import_stats

        self._lock = threading.Lock()

    def deduplicate_contacts(contacts):
        seen_emails = set()

        for contact in contacts:
            if is_duplicate(contact["email"], seen_emails):
                continue

            seen_emails.add(contact["email"])

            yield contact

    def sanitize_contacts(self, contacts: list):
        seen_emails = set()

        for contact in contacts:
            try:
                validated_contact = validate_contact(contact)
            except ValidationError as e:
                self.import_stats.record_validation_error()
                self.log_to_dlq([contact], str(e).replace("\n", " | ").strip())
                continue

            if is_duplicate(validated_contact["email"], seen_emails):
                continue

            seen_emails.add(contact["email"])

            yield validated_contact

    def stream_csv_contacts(self) -> Generator[dict]:
        """Import csv data and return an array of contacts with deduplication"""
        try:
            with open(
                self.contacts_file, mode="r", newline="", encoding="utf-8"
            ) as file:
                reader = csv.DictReader(file)

                yield from self.sanitize_contacts(reader)

        except Exception as e:
            raise RuntimeError(f"Erro durante o stream do arquivo: {e}")

    def log_to_dlq(self, batch: list, error_msg: str) -> None:
        """Log into DLQ file with an new error column"""
        try:
            with self._lock:
                file_exists = os.path.isfile(self.dlq_file)
                with open(
                    self.dlq_file,
                    mode="a",
                    newline="",
                    encoding="utf-8",
                ) as file:
                    if batch:
                        # Include the new error column into the csv headline
                        fieldnames = list(batch[0].keys()) + ["error_log"]
                        writer = csv.DictWriter(file, fieldnames=fieldnames)

                        if not file_exists:
                            writer.writeheader()

                        for row in batch:
                            row["error_log"] = str(error_msg)
                            writer.writerow(row)
        except Exception as e:
            raise RuntimeError(f"Falha ao escrever no DLQ: {e}")
