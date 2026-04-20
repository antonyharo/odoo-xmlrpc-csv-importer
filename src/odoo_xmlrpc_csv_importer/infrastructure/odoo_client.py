import threading
import xmlrpc.client
from typing import Any

from pydantic import HttpUrl
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from odoo_xmlrpc_csv_importer.infrastructure.logger import logger


class OdooClient:
    def __init__(self, *, url: HttpUrl, db: str, username: str, password: str):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self._thread_local = threading.local()

    @property
    def models(self):
        if not hasattr(self._thread_local, "proxy"):
            self._thread_local.proxy = xmlrpc.client.ServerProxy(
                f"{self.url}/xmlrpc/2/object"
            )
        return self._thread_local.proxy

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def authenticate(self) -> None:
        """authenticate the user information to return uid"""
        try:
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            uid = common.authenticate(self.db, self.username, self.password, {})

            if not uid:
                raise ValueError("Failed to Authenticate. Check the credentials.")

            self.uid = uid

        except Exception as e:
            logger.info(f"Authentication Error: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def get_country_id(self, country_name: str):
        """get the country id based on the country name"""
        country_ids: Any = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "res.country",
            "search",
            [[("name", "=", country_name)]],
        )
        return country_ids[0] if country_ids else False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def get_state_id(self, country_id, state_name: str):
        """get the state id based on the state name"""
        state_ids: Any = self.models.execute_kw(
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
    def get_states_and_countries_ids(self) -> dict:
        logger.info("fetching_states_and_countries_ids_from_odoo")

        countries_raw: Any = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "res.country",
            "search_read",
            [[]],
            {"fields": ["name", "id"]},
        )
        countries = {c["name"]: c["id"] for c in countries_raw}

        states_raw: Any = self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            "res.country.state",
            "search_read",
            [[]],
            {"fields": ["name", "id", "country_id"]},
        )
        states = {(s["country_id"][0], s["name"]): s["id"] for s in states_raw}

        return {"countries": countries, "states": states}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def search_emails(self, emails_to_search: set) -> set:
        results: Any = (
            self.models.execute_kw(
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

        return {r["email"].lower() for r in results if r.get("email")}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def create_contacts(self, contacts: list) -> None:
        """Create contacts in Odoo database"""
        self.models.execute_kw(
            self.db, self.uid, self.password, "res.partner", "create", [contacts]
        )
