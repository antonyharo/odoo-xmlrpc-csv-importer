import threading
from typing import Tuple

from odoo_xmlrpc_csv_importer.infrastructure.logger import logger


class ReferenceCache:
    def __init__(self):
        self._countries: dict = {}
        self._states: dict = {}
        self._lock = threading.Lock()

    def warm_up(self, data: dict) -> None:
        with self._lock:
            self._countries = data["countries"]
            self._states = data["states"]
            logger.info(
                "cache_warmed_up",
                countries=len(self._countries),
                states=len(self._states),
            )

    def get_contact_reference_ids(
        self, state_name: str | None, country_name: str, odoo_client
    ) -> Tuple[int | None, int | None]:
        country_name, state_name = self._normalize_inputs(country_name, state_name)

        is_hit, c_id, s_id = self._check_cache_hit(country_name, state_name)
        if is_hit:
            return c_id, s_id

        with self._lock:
            return self._perform_fallback_with_double_check(
                c_id, country_name, state_name, odoo_client
            )

    def _normalize_inputs(
        self, country_name: str, state_name: str | None
    ) -> Tuple[str, str | None]:
        clean_country = country_name.strip()
        clean_state = state_name.strip() if state_name else None
        return clean_country, clean_state

    def _check_cache_hit(
        self, country_name: str, state_name: str | None
    ) -> Tuple[bool, int | None, int | None]:
        # 1. Se a CHAVE não existe, é um Cache Miss verdadeiro.
        if country_name not in self._countries:
            return False, None, None

        c_id = self._countries[country_name]

        # Negative cache - the key existings, but its value is None
        if c_id is None:
            return True, None, None

        if not state_name:
            return True, c_id, None

        state_key = (c_id, state_name)
        if state_key not in self._states:
            return False, c_id, None

        # Pode ser um ID real ou um Negative Cache do estado (None)
        s_id = self._states[state_key]
        return True, c_id, s_id

    def _perform_fallback_with_double_check(
        self,
        cached_c_id: int | None,
        country_name: str,
        state_name: str | None,
        odoo_client,
    ) -> Tuple[int | None, int | None]:
        # Double-check
        is_hit, c_id, s_id = self._check_cache_hit(country_name, state_name)
        if is_hit:
            return c_id, s_id

        logger.warning(
            "cache_miss_performing_fallback", country=country_name, state=state_name
        )

        c_id = c_id or cached_c_id

        return self._fetch_and_update(c_id, country_name, state_name, odoo_client)

    def _fetch_and_update(
        self,
        c_id: int | None,
        country_name: str,
        state_name: str | None,
        odoo_client,
    ) -> Tuple[int | None, int | None]:
        try:
            if country_name not in self._countries:
                fetched_c_id = odoo_client.get_country_id(country_name)
                c_id = fetched_c_id if fetched_c_id else None
                self._countries[country_name] = c_id

            s_id = None
            if c_id and state_name:
                state_key = (c_id, state_name)

                if state_key not in self._states:
                    fetched_s_id = odoo_client.get_state_id(c_id, state_name)
                    s_id = fetched_s_id if fetched_s_id else None
                    self._states[state_key] = s_id
                else:
                    s_id = self._states[state_key]

            return c_id, s_id

        except Exception as e:
            logger.error("fallback_search_failed", error=str(e), country=country_name)
            return None, None
