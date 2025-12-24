import xmlrpc.client
import csv
import os
import time
from dotenv import load_dotenv
from get_ids import get_country_id, get_state_id, get_existing_contacts

load_dotenv()

# import csv data and return an array of contacts (com verificação de duplicatas no CSV)
def import_csv_contacts(file_name):
    print(f"Diretório atual: {os.getcwd()}")

    try:
        if not os.path.isfile(file_name):
            print(f"Arquivo '{file_name}' não encontrado no diretório atual.")
            return

        with open(file_name, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            contacts = []
            invalid_contacts = []

            # control sets to avoid duplicated contacts
            seen_names = set()
            seen_emails = set()

            print("\nRegistros válidos do arquivo:")

            # get the contact info from the csv file
            for row_index, row in enumerate(reader, start=1):
                contact_name = (row.get("Nome completo") or "").strip()
                contact_email = (row.get("E-mail") or "").strip()

                # check if the name or email is alredy in the sets
                if contact_name in seen_names or contact_email in seen_emails:
                    continue

                # add the name and email to the sets variables
                seen_names.add(contact_name)
                seen_emails.add(contact_email)

                contact = {
                    # default res.partner fields
                    "name": contact_name,
                    "email": contact_email,
                    "function": (row.get("Cargo") or "").strip(),
                    "company_name": (row.get("Nome da empresa") or "").strip(),
                    "city": (row.get("Cidade") or "").strip(),
                    "country_id": (row.get("País") or "").strip(),
                    "state_id": (row.get("Estado") or "").strip(),
                    "street": (row.get("Localização") or "").strip(),
                    "website": (row.get("LinkedIn") or "").strip(),
                }

                if not contact["name"] or not contact["email"]:
                    invalid_contacts.append(
                        f"Registro {row_index}, {contact['name']}, {contact['email']}"
                    )
                    continue

                print(
                    f"Registro {row_index}, Nome: {contact['name']}, Email: {contact['email']}"
                )
                contacts.append(contact)

            if invalid_contacts:
                print("\nRegistros inválidos:")
                for i in invalid_contacts:
                    print(i)

            return contacts

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


# verify if the contact alredy exists in the odoo database
def contact_exists_odoo(existing_contacts, contact):
    for existing_contact in existing_contacts:
        if (
            existing_contact["name"] == contact["name"]
            or existing_contact["email"] == contact["email"]
        ):
            return True
    return False


# cache dictionaries for the country and state
country_cache = {}
state_cache = {}


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


# create the contacts using the cache feature
def create_contacts(url, db, uid, password, contacts):
    try:
        models = xmlrpc.client.ServerProxy("{}/xmlrpc/2/object".format(url))
        existing_contacts = get_existing_contacts(models, db, uid, password)

        for contact in contacts:
            if contact_exists_odoo(existing_contacts, contact):
                print(
                    f"{contact['name']} ou o email {contact['email']} já existe em seu banco de dados."
                )
                continue

            country_id = get_country_id_cached(
                models, db, uid, password, contact["country_id"]
            )
            state_id = get_state_id_cached(
                models, db, uid, password, country_id, contact["state_id"]
            )

            contact["state_id"] = state_id or ""
            contact["country_id"] = country_id or ""

            contact_id = models.execute_kw(
                db, uid, password, "res.partner", "create", [contact]
            )
            print(f"{contact['name']} criado com o ID: {contact_id}")

    except Exception as e:
        print(f"Erro ao criar contatos: {e}")


def main():
    # get the credentials
    odoo_url = os.getenv("ODOO_URL")
    odoo_db = os.getenv("ODOO_DB")
    odoo_username = os.getenv("ODOO_USERNAME")
    odoo_password = os.getenv("ODOO_PASSWORD")

    # try to authenticate the user and get the uid
    uid = authenticate(odoo_url, odoo_db, odoo_username, odoo_password)
    if uid:
        # get the contacts from csv
        contacts = import_csv_contacts("test.csv")

        if contacts:
            print(f"\nTotal de contatos para serem carregados: {len(contacts)}\n")

            # create contacts from the array of contacts
            create_contacts(odoo_url, odoo_db, uid, odoo_password, contacts)


if __name__ == "__main__":
    start_time = time.time()  # register the time
    main()
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(
        f"Tempo de execução: {elapsed_time:.2f} segundos"
    )  # print the execution time of the main()
