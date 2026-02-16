import csv
import os
import threading
import time
import xmlrpc.client
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from get_ids import get_country_id, get_state_id
from utils import chunker

load_dotenv()
file_lock = threading.Lock()

DLQ_FILE = "failed_records.csv"

country_cache = {}
state_cache = {}

total_contacts_created = 0  # this will be used as a counter


# import csv data and return an array of contacts (com verificação de duplicatas no CSV)
def stream_csv_contacts(file_name):
    try:
        with open(file_name, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            # control sets to avoid duplicated contacts
            seen_emails = set()

            # get the contact info from the csv file
            for row in reader:
                contact_email = (row.get("E-mail") or "").strip()

                if not row.get("E-mail") or not row.get("Nome completo"):
                    continue

                # check if the name or email is alredy in the sets
                if contact_email in seen_emails:
                    continue

                # add the name and email to the sets variables
                seen_emails.add(contact_email)

                yield {
                    # default res.partner fields
                    "name": (row.get("Nome completo") or "").strip(),
                    "email": contact_email,
                    "function": (row.get("Cargo") or "").strip(),
                    "company_name": (row.get("Nome da empresa") or "").strip(),
                    "city": (row.get("Cidade") or "").strip(),
                    "country_id": (row.get("País") or "").strip(),
                    "state_id": (row.get("Estado") or "").strip(),
                    "street": (row.get("Localização") or "").strip(),
                    "website": (row.get("LinkedIn") or "").strip(),
                }

    except Exception as e:
        print(f"Erro ao carregar o arquivo: {e}")


# authenticate the user information to return uid
def authenticate(url, db, username, password):
    try:
        common = xmlrpc.client.ServerProxy("{}/xmlrpc/2/common".format(url))
        uid = common.authenticate(db, username, password, {})

        if not uid:
            raise ValueError("Falha na autenticação. Verifique as credenciais.")
        return uid

    except Exception as e:
        print(f"Erro ao autenticar: {e}")


# check if the country_id already exists or search and save in the cache
def get_country_id_cached(models, db, uid, password, country_name):
    if country_name in country_cache:
        return country_cache[country_name]

    country_id = get_country_id(models, db, uid, password, country_name)
    if country_id:
        country_cache[country_name] = country_id

    return country_id


# check if the state_id already exists or search and save in the cache
def get_state_id_cached(models, db, uid, password, country_id, state_name):
    # creates a unique key using the country and state, making sure states with the same name in different countries are treated separately
    state_cache_key = (country_id, state_name)

    if state_cache_key in state_cache:
        return state_cache[state_cache_key]

    state_id = get_state_id(models, db, uid, password, country_id, state_name)
    if state_id:
        state_cache[state_cache_key] = state_id

    return state_id


def log_to_dlq(batch, error_msg):
    with file_lock:  # Só uma thread escreve por vez
        file_exists = os.path.isfile(DLQ_FILE)
        try:
            with open(DLQ_FILE, mode="a", newline="", encoding="utf-8") as file:
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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry_error_callback=lambda retry_state: retry_state.outcome.result(),  # type: ignore
)
def create_contacts_with_retry(db, url, uid, password, contacts):
    # global total_contacts_created

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
            models, db, uid, password, contact["country_id"]
        )
        state_id = get_state_id_cached(
            models, db, uid, password, country_id, contact["state_id"]
        )

        contact["country_id"] = country_id if country_id else False
        contact["state_id"] = state_id if state_id else False

        contacts_to_create.append(contact)

    if contacts_to_create:
        models.execute_kw(
            db, uid, password, "res.partner", "create", [contacts_to_create]
        )

        return len(contacts_to_create)  # sucess

    return 0


def process_batch_safe(db, url, uid, password, batch):
    """Wrapper para capturar falhas finais e jogar na DLQ"""
    try:
        count = create_contacts_with_retry(db, url, uid, password, batch)
        print(f"Lote processado: {count} criados.")
    except Exception as e:
        print(f"ERRO FINAL NO LOTE: {e} -> Enviando para DLQ...")
        log_to_dlq(batch, str(e))


def main(file_name):
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
        # get the contacts from csv
        contacts_stream = stream_csv_contacts(file_name)

        print("\nCarregando lotes...")

        with ThreadPoolExecutor(max_workers=4) as executor:
            # create contacts in batches to avoid overload in odoo or local memory
            for batch in chunker(contacts_stream, 1000):
                executor.submit(
                    process_batch_safe,
                    db,
                    url,
                    uid,
                    password,
                    batch,
                )

        print("\nImportação finalizada! ;)")
        # print(f"Total de novos contatos no banco: {total_contacts_created}\n")


if __name__ == "__main__":
    start_time = time.time()
    main("stress_test.csv")
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(
        f"Tempo de execução: {elapsed_time:.2f} segundos"
    )  # print the execution time of the main()
