from rpc import get_country_id, get_state_id


def get_state_id_cached(
    *, models, db, uid, password, country_id, state_name, state_cache
):
    """check if the state_id already exists or search and save in the cache"""
    # creates a unique key using the country and state, making sure states with the same name in different countries are treated separately
    state_cache_key = (country_id, state_name)

    if state_cache_key in state_cache:
        return state_cache[state_cache_key]

    state_id = get_state_id(models, db, uid, password, country_id, state_name)
    if state_id:
        state_cache[state_cache_key] = state_id

    return state_id


def get_country_id_cached(*, models, db, uid, password, country_name, country_cache):
    """check if the country_id already exists or search and save in the cache"""
    if country_name in country_cache:
        return country_cache[country_name]

    country_id = get_country_id(models, db, uid, password, country_name)
    if country_id:
        country_cache[country_name] = country_id

    return country_id
