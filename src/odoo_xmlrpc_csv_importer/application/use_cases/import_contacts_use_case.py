import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Generator

from pydantic import ValidationError

from odoo_xmlrpc_csv_importer.domain.contact import is_duplicate, validate_contact
from odoo_xmlrpc_csv_importer.infrastructure.import_stats import ImportStats
from odoo_xmlrpc_csv_importer.infrastructure.logger import logger
from odoo_xmlrpc_csv_importer.infrastructure.odoo_client import OdooClient
from odoo_xmlrpc_csv_importer.utils.chunker import chunker


class ImportContactsUseCase:
    def __init__(
        self,
        csv_reader,
        dlq_writer,
        odoo_client: OdooClient,
        reference_cache,
        import_stats: ImportStats,
    ):
        self.csv_reader = csv_reader
        self.dlq_writer = dlq_writer
        self.odoo_client = odoo_client
        self.reference_cache = reference_cache
        self.stats = import_stats
        self._seen_emails = set()

    def execute(self, file_path: str, max_workers: int, batch_size: int) -> None:
        logger.info("start_import_contacts_use_case", file=str(file_path))

        valid_stream = self._stream_and_validate_data()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []

            for batch in chunker(valid_stream, batch_size):
                futures.append(executor.submit(self._process_batch, batch))

            for fut in as_completed(futures):
                fut.result()

    def _stream_and_validate_data(self) -> Generator[Dict[str, Any], None, None]:
        """Read CSV, remove invalid or duplicated rows in memory and send to DLQ"""
        for raw_contact in self.csv_reader.stream():
            try:
                contact = validate_contact(raw_contact)
            except ValidationError as e:
                self.stats.record_validation_error()
                self.dlq_writer.write_errors([raw_contact], str(e).replace("\n", " "))
                continue

            if is_duplicate(contact["email"], self._seen_emails):
                self.stats.record_duplicate_contact()
                continue

            self._seen_emails.add(contact["email"])
            yield contact

    def _process_batch(self, batch: list) -> None:
        """Each thread use this method, it handles with cache, Odoo and DLQ"""
        self.stats.worker_enter()
        start_time = time.time()

        try:
            existing_emails = self.odoo_client.search_emails(
                {c["email"] for c in batch}
            )

            new_contacts = [c for c in batch if c["email"] not in existing_emails]
            enriched_contacts = self._enrich_contacts(new_contacts)

            if enriched_contacts:
                self.odoo_client.create_contacts(enriched_contacts)

            skipped = len(batch) - len(enriched_contacts)
            self.stats.record_batch_success(
                created=len(enriched_contacts), skipped_odoo=skipped
            )

            logger.debug(
                "batch_processed",
                created=len(enriched_contacts),
                ignored=skipped,
                time=round(time.time() - start_time, 2),
            )

        except Exception as e:
            logger.error("batch_failure", error=str(e))
            self.dlq_writer.write_errors(batch, str(e))
            self.stats.record_batch_failure(len(batch))

        finally:
            self.stats.worker_exit()

    def _enrich_contacts(self, contacts: list) -> list:
        enriched = []
        for c in contacts:
            if c["country_id"]:
                c["country_id"], c["state_id"] = (
                    self.reference_cache.get_contact_reference_ids(
                        state_name=c["state_id"],
                        country_name=c["country_id"],
                        odoo_client=self.odoo_client,
                    )
                )

                if not c["state_id"]:
                    c["state_id"] = False

                if not c["country_id"]:
                    c["country_id"] = False

            enriched.append(c)
        return enriched
