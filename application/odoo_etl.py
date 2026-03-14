import os
import threading
import xmlrpc.client
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

import typer
from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from cache import get_country_id_cached, get_state_id_cached
from infrastructure.csv_manager import CsvManager
from rpc import authenticate
from utils import chunker

load_dotenv()
file_lock = threading.Lock()

DLQ_FILE = "failed_records.csv"

COUNTRY_CACHE = {}
STATE_CACHE = {}

app = typer.Typer()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry_error_callback=lambda retry_state: retry_state.outcome.result(),  # type: ignore
)
def load_contacts(db, url, uid, password, contacts):
    # CADA THREAD CRIA SEU PRÓPRIO PROXY (Isolamento de Socket)
    models = xmlrpc.client.ServerProxy("{}/xmlrpc/2/object".format(url))

    contacts_to_create: list[dict] = []

    set_emails_csv = {c["email"] for c in contacts}  # type: ignore

    # target search
    records_db = models.execute_kw(
        db,
        uid,
        password,
        "res.partner",
        "search_read",
        [[["email", "in", list(set_emails_csv)]]],
        {"fields": ["email"]},
    )

    set_emails_db = {r["email"] for r in records_db if r.get("email")}  # type: ignore

    # sanitize data to contain ids or to identidy if already exists in db
    for contact in contacts:
        if contact["email"] in set_emails_db:
            continue

        # O cache global (dicts) é thread-safe em Python para operações simples
        # Mas em produção pesada, usaríamos um Lock. Para agora, está ok.
        country_id = get_country_id_cached(
            models=models,
            db=db,
            uid=uid,
            password=password,
            country_name=contact["country_id"],
            country_cache=COUNTRY_CACHE,
        )
        state_id = get_state_id_cached(
            models=models,
            db=db,
            uid=uid,
            password=password,
            country_id=country_id,
            state_name=contact["state_id"],
            state_cache=STATE_CACHE,
        )

        contact["country_id"] = country_id if country_id else False
        contact["state_id"] = state_id if state_id else False

        contacts_to_create.append(contact)

    if contacts_to_create:
        models.execute_kw(
            db, uid, password, "res.partner", "create", [contacts_to_create]
        )

        return len(contacts_to_create)

    return 0


def load_contacts_safe(db, url, uid, password, batch, csv_manager):
    """Wrapper para capturar falhas finais e jogar na DLQ"""
    try:
        count = load_contacts(db, url, uid, password, batch)
        print(f"Lote processado: {count} criados.")
    except Exception as e:
        print(f"ERRO FINAL NO LOTE: {e} -> Enviando para DLQ...")
        csv_manager.log_to_dlq(DLQ_FILE, batch, str(e))


def odoo_etl(file_name, max_workers, batch_size):
    # get the credentials
    url = os.getenv("ODOO_URL")
    db = os.getenv("ODOO_DB")
    username = os.getenv("ODOO_USERNAME")
    password = os.getenv("ODOO_PASSWORD")

    print("\nBem vindo ao importador de contatos .CSV!")

    print(f"\nDiretório atual: {os.getcwd()}")
    if not os.path.isfile(file_name):
        print(f"Arquivo '{file_name}' não encontrado no diretório atual.")
        return

    # try to authenticate the user and get the uid
    uid = authenticate(url, db, username, password)
    if uid:
        csv_manager = CsvManager(file_name)
        contacts_stream = csv_manager.stream_csv_contacts(file_name)

        print("\nCarregando lotes...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # create contacts in batches to avoid overload in odoo or local memory
            for batch in chunker(contacts_stream, batch_size):
                executor.submit(
                    load_contacts_safe,
                    db,
                    url,
                    uid,
                    password,
                    batch,
                    csv_manager
                )

        print("\nImportação finalizada! ;)")