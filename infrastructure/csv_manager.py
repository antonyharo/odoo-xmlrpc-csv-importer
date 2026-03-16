import threading
import csv
import os

file_lock = threading.Lock()


class CsvManager:
    def __init__(self, contacts_file: str, dlq_file: str) -> None:
        self.contacts_file = contacts_file
        self.dlq_file = dlq_file

    def stream_csv_contacts(self):
        """import csv data and return an array of contacts with deduplication"""
        try:
            with open(self.contacts_file, mode="r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)

                seen_emails = set()

                for row in reader:
                    contact_email = (row.get("email") or "").strip()

                    # if the contact is not valid, send to an separated file -> problematic data                        
                    if not row.get("email") or not row.get("name"):
                        continue

                    if contact_email in seen_emails:
                        continue

                    seen_emails.add(contact_email)

                    yield row

        except Exception as e:
            print(f"Erro ao carregar o arquivo: {e}")

    def log_to_dlq(self, batch: list, error_msg: str):
        with file_lock:
            file_exists = os.path.isfile(self.dlq_file)
            try:
                with open(self.dlq_file, mode="a", newline="", encoding="utf-8") as file:
                    if batch:
                        # Garantimos que o cabeçalho inclua a nova coluna de erro
                        fieldnames = list(batch[0].keys()) + ["error_log"]
                        writer = csv.DictWriter(file, fieldnames=fieldnames)

                        if not file_exists:
                            writer.writeheader()

                        for row in batch:
                            row["error_log"] = str(error_msg)
                            writer.writerow(row)
            except Exception as e:
                print(f"CRÍTICO: Falha ao escrever no DLQ: {e}")