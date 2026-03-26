import threading
import time
import xmlrpc.client
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from odoo_xmlrpc_csv_importer.infrastructure.csv_manager import CsvManager
from odoo_xmlrpc_csv_importer.infrastructure.odoo_client import OdooClient
from odoo_xmlrpc_csv_importer.services.reference_cache import ReferenceCache
from odoo_xmlrpc_csv_importer.utils.utils import chunker

DLQ_FILE = "failed_records.csv"

COUNTRY_CACHE = {}
STATE_CACHE = {}

file_lock = threading.Lock()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry_error_callback=lambda retry_state: retry_state.outcome.result(),  # type: ignore
)
def create_contacts(odoo_client: OdooClient, batch: list, csv_manager: CsvManager):
    """Load CSV records on Odoo"""

    try:
        # Each thread creates its own proxy
        models = xmlrpc.client.ServerProxy(f"{odoo_client.url}/xmlrpc/2/object")

        contacts_to_create: list[dict] = []

        set_emails_csv: set = {c["email"] for c in batch}

        records_db: list = odoo_client.search_records(models, set_emails_csv)
        set_emails_db: set = {r["email"] for r in records_db if r.get("email")}

        # sanitize data to contain ids or to identify if already exists in db
        for contact in batch:
            if contact["email"] in set_emails_db:
                continue

            # Thread safe in local env
            reference_cache = ReferenceCache(COUNTRY_CACHE, STATE_CACHE)

            country_id = reference_cache.get_country_id_cached(
                models=models,
                country_name=contact["country_id"],
                get_country_id=odoo_client.get_country_id,
            )

            state_id = reference_cache.get_state_id_cached(
                models=models,
                country_id=country_id,
                state_name=contact["state_id"],
                get_state_id=odoo_client.get_state_id,
            )

            contact["country_id"] = country_id if country_id else False
            contact["state_id"] = state_id if state_id else False

            contacts_to_create.append(contact)

        print(f"Lote processado: {len(contacts_to_create) | 0} criados.")
    except Exception as e:
        print(f"Erro no lote: {e}")
        csv_manager.log_to_dlq(batch, str(e))


def odoo_etl(settings, file: Path, max_workers: int, batch_size: int) -> None:
    start_time = time.time()


    print(f"Lendo arquivo de: {file}")

    odoo_client = OdooClient(
        url=settings.url,
        db=settings.db,
        username=settings.username,
        password=settings.password.get_secret_value(),
    )

    if odoo_client.uid:
        csv_manager = CsvManager(file, DLQ_FILE)
        contacts_stream = csv_manager.stream_csv_contacts()

        print("\nCarregando lotes...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # create contacts in batches to avoid overload in odoo or local memory
            for batch in chunker(contacts_stream, batch_size):
                executor.submit(create_contacts, odoo_client, batch, csv_manager)

        print("\nImportação finalizada.")

    end_time = time.time()
    elapsed_time = end_time - start_time

    print(f"Tempo de execução: {elapsed_time:.2f} segundos")
