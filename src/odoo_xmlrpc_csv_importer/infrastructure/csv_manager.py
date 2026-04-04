import csv
import os
import threading
from pathlib import Path
from typing import Generator

from pydantic import ValidationError

from odoo_xmlrpc_csv_importer.domain.contact import is_duplicate, validate_contact


class CsvManager:
    def __init__(self, contacts_file: Path, dlq_file: str) -> None:
        self.contacts_file = contacts_file
        self.dlq_file = dlq_file

        self.file_lock = threading.Lock()

    # def process_raw_contact(self, raw_contact, seen_emails) -> dict | None:
    #     try:
    #         validated_contact = validate_contact(raw_contact)

    #         if is_duplicate(validated_contact["email"], seen_emails):
    #             return None

    #         return validated_contact
    #     except ValidationError as e:
    #         self.log_to_dlq([raw_contact], str(e).replace("\n", " | ").strip())
    #         return None

    def stream_csv_contacts(self) -> Generator[dict]:
        """Import csv data and return an array of contacts with deduplication"""
        try:
            with open(
                self.contacts_file, mode="r", newline="", encoding="utf-8"
            ) as file:
                reader = csv.DictReader(file)

                seen_emails = set()

                for row in reader:
                    try:
                        validated_contact = validate_contact(row)
                    except ValidationError as e:
                        self.log_to_dlq([row], str(e).replace("\n", " | ").strip())
                        continue

                    if is_duplicate(validated_contact["email"], seen_emails):
                        continue

                    seen_emails.add(validated_contact["email"])

                    yield validated_contact

        except Exception as e:
            raise RuntimeError(f"Erro durante o stream do arquivo: {e}")

    def log_to_dlq(self, batch: list, error_msg: str) -> None:
        """Log into DLQ file with an new error column"""
        try:
            with self.file_lock:
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
