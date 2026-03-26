class ReferenceCache:
    def __init__(self, country_cache, state_cache):
        self.country_cache = country_cache
        self.state_cache = state_cache

    def get_state_id_cached(self, *, models, country_id, state_name, get_state_id):
        """Check if the state_id already exists or search and save in the cache"""

        # Creates a unique key using the country and state, making sure states with the same name in different countries are treated separately
        state_cache_key = (country_id, state_name)

        if state_cache_key in self.state_cache:
            return self.state_cache[state_cache_key]

        state_id = get_state_id(models, country_id, state_name)
        if state_id:
            self.state_cache[state_cache_key] = state_id

        return state_id

    def get_country_id_cached(self, *, models, country_name, get_country_id):
        """Check if the country_id already exists or search and save in the cache"""
        if country_name in self.country_cache:
            return self.country_cache[country_name]

        country_id = get_country_id(models, country_name)
        if country_id:
            self.country_cache[country_name] = country_id

        return country_id

    def get_contact_reference_ids(
        self, *, models, country_name: str, state_name: str, odoo_client
    ) -> tuple:
        """Get reference IDs to the contact based on existing cache"""
        country_id = self.get_country_id_cached(
            models=models,
            country_name=country_name,
            get_country_id=odoo_client.get_country_id,
        )

        state_id = self.get_state_id_cached(
            models=models,
            country_id=country_id,
            state_name=state_name,
            get_state_id=odoo_client.get_state_id,
        )

        return country_id if country_id else False, state_id if state_id else False
