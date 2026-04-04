import time
import xmlrpc.client
from concurrent.futures import ThreadPoolExecutor

from odoo_xmlrpc_csv_importer.core.chunker import chunker
from odoo_xmlrpc_csv_importer.infrastructure.logger import logger


def search_existing_emails(batch: list, models, odoo_client) -> set:
    emails_to_search: set = {c["email"] for c in batch}

    records_db: list = odoo_client.search_records(models, emails_to_search)
    return {r["email"].lower() for r in records_db if r.get("email")}


def process_batch(batch: list, odoo_client, csv_manager, reference_cache) -> None:
    """Process batch of contacts and orquestrates deduplication, cache and load in Odoo"""
    try:
        start_time = time.time()

        contacts_to_create: list[dict] = []

        # Each thread creates its own models proxy
        models = xmlrpc.client.ServerProxy(f"{odoo_client.url}/xmlrpc/2/object")

        existing_emails: set = search_existing_emails(batch, models, odoo_client)

        # Sanitize data to get reference ids and filter records that already exists in db
        for contact in batch:
            if contact["email"] in existing_emails:
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

        logger.info(
            f"Lote processado: {len(contacts_to_create)} contatos criados em {time.time() - start_time:.2f} segundos."
        )

    except Exception as e:
        logger.error(f"Erro no lote: {e}")
        csv_manager.log_to_dlq(batch, str(e))


def import_contacts(
    *,
    file_name,
    max_workers: int,
    batch_size: int,
    odoo_client,
    csv_manager,
    reference_cache,
) -> None:
    start_time = time.time()

    logger.info(f"Lendo arquivo de: {file_name}")

    if odoo_client.uid:
        contacts_stream = csv_manager.stream_csv_contacts()

        logger.info("Carregando lotes...")

        # Create contacts in batches to avoid overload in odoo or local memory
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for batch in chunker(contacts_stream, batch_size):
                executor.submit(
                    process_batch, batch, odoo_client, csv_manager, reference_cache
                )

        logger.info("Importação finalizada.")

    logger.info(f"Tempo de execução: {time.time() - start_time:.2f} segundos")
