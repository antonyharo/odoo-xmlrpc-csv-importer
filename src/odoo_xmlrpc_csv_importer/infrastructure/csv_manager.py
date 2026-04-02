import csv
import os
import threading
from pathlib import Path
from typing import Generator

from pydantic import ValidationError

from odoo_xmlrpc_csv_importer.domain.contact import ContactSchema

file_lock = threading.Lock()


class CsvManager:
    def __init__(self, contacts_file: Path, dlq_file: str) -> None:
        self.contacts_file = contacts_file
        self.dlq_file = dlq_file

    def _validate_contact(self, row: dict, seen_emails: set) -> dict:
        try:
            contact = ContactSchema(**row)

            if contact.email in seen_emails:
                return {}

            return contact.model_dump(mode="json")
        except ValidationError as e:
            if ValidationError:
                self.log_to_dlq(
                    [row], f"Erro de validação de Schema: {str(e.errors())}"
                )

            return {}

    def stream_csv_contacts(self) -> Generator[dict]:
        """Import csv data and return an array of contacts with deduplication"""
        try:
            with open(
                self.contacts_file, mode="r", newline="", encoding="utf-8"
            ) as file:
                reader = csv.DictReader(file)

                seen_emails = set()

                for row in reader:
                    validated_contact: dict = self._validate_contact(row, seen_emails)

                    if not validated_contact:
                        continue

                    seen_emails.add(validated_contact["email"])

                    yield validated_contact

        except Exception as e:
            raise RuntimeError(f"Erro durante o stream do arquivo: {e}")

    def log_to_dlq(self, batch: list, error_msg: str) -> None:
        """Log into DLQ file with an new error column"""
        try:
            with file_lock:
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
