import xmlrpc.client

from pydantic import HttpUrl
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)


class OdooClient:
    def __init__(self, *, url: HttpUrl, db: str, username: str, password: str):
        self.url: HttpUrl = url
        self.db: str = db
        self.username: str = username
        self.password: str = password

        self.uid = self.authenticate()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def authenticate(self):
        """authenticate the user information to return uid"""
        try:
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            uid = common.authenticate(self.db, self.username, self.password, {})

            if not uid:
                raise ValueError("Falha na autenticação. Verifique as credenciais.")
            return uid

        except Exception as e:
            print(f"Erro ao autenticar: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def get_country_id(self, models, country_name: str):
        """get the country id based on the country name"""
        country_ids = models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "res.country",
            "search",
            [[("name", "=", country_name)]],
        )
        return country_ids[0] if country_ids else False  # type: ignore

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def get_state_id(self, models, country_id, state_name: str):
        """get the state id based on the state name"""
        state_ids = models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "res.country.state",
            "search",
            [[("name", "=", state_name), ("country_id", "=", country_id)]],
        )
        return state_ids[0] if state_ids else False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def search_records(self, models, emails_to_search: set) -> list:
        records_db = (
            models.execute_kw(
                self.db,
                self.uid,
                self.password,
                "res.partner",
                "search_read",
                [[["email", "in", list(emails_to_search)]]],
                {"fields": ["email"]},
            )
            or []
        )

        return records_db

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def create_contacts(self, models, contacts):
        """Create contacts in Odoo database"""
        models.execute_kw(
            self.db, self.uid, self.password, "res.partner", "create", [contacts]
        )
