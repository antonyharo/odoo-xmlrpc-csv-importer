import csv
import os
import threading
from pathlib import Path

from pydantic import ValidationError

from odoo_xmlrpc_csv_importer.domain.contact import ContactSchema

file_lock = threading.Lock()


class CsvManager:
    def __init__(self, contacts_file: Path, dlq_file: str) -> None:
        self.contacts_file = contacts_file
        self.dlq_file = dlq_file

    def _validate_contact(self, row, seen_emails) -> dict:
        try:
            contact = ContactSchema(**row)

            if contact.email in seen_emails:
                raise ValueError("Registro já existente no arquivo")

            return contact.model_dump()
        except (ValidationError, ValueError) as e:
            # print(f"Registro inválido: {e}")
            return {}

    def stream_csv_contacts(self):
        """Import csv data and return an array of contacts with deduplication"""
        try:
            with open(
                self.contacts_file, mode="r", newline="", encoding="utf-8"
            ) as file:
                reader = csv.DictReader(file)

                seen_emails = set()

                for row in reader:
                    validated_contact = self._validate_contact(row, seen_emails)

                    if not validated_contact:
                        continue

                    seen_emails.add(validated_contact["email"])

                    yield row

        except Exception as e:
            raise RuntimeError(f"Erro durante o stream do arquivo: {e}")

    def log_to_dlq(self, batch: list, error_msg: str):
        """Log into DLQ file with an new error column"""
        with file_lock:
            file_exists = os.path.isfile(self.dlq_file)
            try:
                with open(
                    self.dlq_file, mode="a", newline="", encoding="utf-8"
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
                print(f"CRÍTICO: Falha ao escrever no DLQ: {e}")
