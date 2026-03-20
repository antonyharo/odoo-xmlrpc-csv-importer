import os
import threading
import time
import xmlrpc.client
from concurrent.futures import ThreadPoolExecutor

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from odoo_xmlrpc_csv_importer.infrastructure.csv_manager import CsvManager
from odoo_xmlrpc_csv_importer.infrastructure.odoo_client import OdooClient
from odoo_xmlrpc_csv_importer.services.reference_cache import ReferenceCache
from odoo_xmlrpc_csv_importer.utils.utils import chunker, require_env

DLQ_FILE = "failed_records.csv"

COUNTRY_CACHE = {}
STATE_CACHE = {}

file_lock = threading.Lock()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry_error_callback=lambda retry_state: retry_state.outcome.result(),  # type: ignore
)
def load_contacts(odoo_client, contacts):
    """Load CSV records on Odoo"""

    # Each thread creates its own proxy
    models = xmlrpc.client.ServerProxy("{}/xmlrpc/2/object".format(odoo_client.url))

    contacts_to_create: list[dict] = []

    set_emails_csv = {c["email"] for c in contacts}

    records_db = odoo_client.search_records(models, set_emails_csv)
    set_emails_db = {r["email"] for r in records_db if r.get("email")}  # type: ignore

    # sanitize data to contain ids or to identify if already exists in db
    for contact in contacts:
        if contact["email"] in set_emails_db:
            continue

        # O cache global (dicts) é thread-safe em Python para operações simples
        # Mas em produção pesada, usaríamos um Lock. Para agora, está ok.

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

    if contacts_to_create:
        odoo_client.create_contacts(models, contacts_to_create)

        return len(contacts_to_create)

    return 0


def load_contacts_safe(odoo_client, batch, csv_manager):
    """Wrapper para capturar falhas finais e jogar na DLQ"""
    try:
        count = load_contacts(odoo_client, batch)
        print(f"Lote processado: {count} criados.")
    except Exception as e:
        print(f"ERRO FINAL NO LOTE: {e} -> Enviando para DLQ...")
        csv_manager.log_to_dlq(DLQ_FILE, batch, str(e))


def odoo_etl(file_name, max_workers, batch_size):
    start_time = time.time()
    url = require_env("ODOO_URL")
    db = require_env("ODOO_DB")
    username = require_env("ODOO_USERNAME")
    password = require_env("ODOO_PASSWORD")

    print("\nBem vindo ao importador de contatos .CSV!")

    print(f"\nDiretório atual: {os.getcwd()}")
    if not os.path.isfile(file_name):
        print(f"Arquivo '{file_name}' não encontrado no diretório atual.")
        return

    odoo_client = OdooClient(url=url, db=db, username=username, password=password)

    if odoo_client:
        csv_manager = CsvManager(file_name, DLQ_FILE)
        contacts_stream = csv_manager.stream_csv_contacts()

        print("\nCarregando lotes...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # create contacts in batches to avoid overload in odoo or local memory
            for batch in chunker(contacts_stream, batch_size):
                executor.submit(load_contacts_safe, odoo_client, batch, csv_manager)

        print("\nImportação finalizada! ;)")

    end_time = time.time()
    elapsed_time = end_time - start_time

    print(f"Tempo de execução: {elapsed_time:.2f} segundos")
