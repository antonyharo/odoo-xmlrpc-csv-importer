import time
import xmlrpc.client
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from odoo_xmlrpc_csv_importer.infrastructure.csv_manager import CsvManager
from odoo_xmlrpc_csv_importer.infrastructure.odoo_client import OdooClient
from odoo_xmlrpc_csv_importer.services.reference_cache import ReferenceCache
from odoo_xmlrpc_csv_importer.utils.utils import chunker

COUNTRY_CACHE = {}
STATE_CACHE = {}


def process_batch(odoo_client: OdooClient, batch: list, csv_manager: CsvManager):
    """Process batch of contacts and orquestrates deduplication, cache and load in Odoo"""
    try:
        start_time = time.time()
        # Each thread creates its own models proxy
        models = xmlrpc.client.ServerProxy(f"{odoo_client.url}/xmlrpc/2/object")

        contacts_to_create: list[dict] = []

        set_search_emails: set = {c["email"] for c in batch}

        records_db: list = odoo_client.search_records(models, set_search_emails)
        set_existing_emails: set = {r["email"] for r in records_db if r.get("email")}

        reference_cache = ReferenceCache(COUNTRY_CACHE, STATE_CACHE)

        # Sanitize data to get reference ids and filter records that already exists in db
        for contact in batch:
            if contact["email"] in set_existing_emails:
                continue

            contact["country_id"], contact["state_id"] = (
                reference_cache.get_contact_reference_ids(
                    state_name=contact["state_id"],
                    country_name=contact["country_id"],
                    odoo_client=odoo_client,
                    models=models,
                )
            )

            contacts_to_create.append(contact)

        if contacts_to_create:
            odoo_client.create_contacts(models, contacts_to_create)

        end_time = time.time()
        total_time = end_time - start_time

        print(
            f"Lote processado: {len(contacts_to_create)} contatos criados em {total_time:.2f} segundos."
        )
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
        csv_manager = CsvManager(file, settings.dql_file)
        contacts_stream = csv_manager.stream_csv_contacts()

        print("\nCarregando lotes...")

        # Create contacts in batches to avoid overload in odoo or local memory
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for batch in chunker(contacts_stream, batch_size):
                executor.submit(process_batch, odoo_client, batch, csv_manager)

        print("\nImportação finalizada.")

    end_time = time.time()
    elapsed_time = end_time - start_time

    print(f"Tempo de execução: {elapsed_time:.2f} segundos")
