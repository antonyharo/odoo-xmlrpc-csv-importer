class CacheManager:
    def __init__(self, country_cache, state_cache):
        self.country_cache = country_cache
        self.state_cache = state_cache

    def get_state_id_cached(
        self, *, models, country_id, state_name, get_state_id
    ):
        """check if the state_id already exists or search and save in the cache"""

        # creates a unique key using the country and state, making sure states with the same name in different countries are treated separately
        state_cache_key = (country_id, state_name)

        if state_cache_key in self.state_cache:
            return self.state_cache[state_cache_key]

        state_id = get_state_id(models, country_id, state_name)
        if state_id:
            self.state_cache[state_cache_key] = state_id

        return state_id

    def get_country_id_cached(
        self, *, models, country_name, get_country_id
    ):
        """check if the country_id already exists or search and save in the cache"""
        if country_name in self.country_cache:
            return self.country_cache[country_name]

        country_id = get_country_id(models, country_name)
        if country_id:
            self.country_cache[country_name] = country_id

        return country_id
