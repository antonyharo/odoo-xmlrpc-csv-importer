import xmlrpc.client


def authenticate(url, db, username, password):
    """authenticate the user information to return uid"""
    try:
        common = xmlrpc.client.ServerProxy("{}/xmlrpc/2/common".format(url))
        uid = common.authenticate(db, username, password, {})

        if not uid:
            raise ValueError("Falha na autenticação. Verifique as credenciais.")
        return uid

    except Exception as e:
        print(f"Erro ao autenticar: {e}")


def get_country_id(models, db, uid, password, country_name):
    """get the country id based on the country name"""
    country_ids = models.execute_kw(
        db, uid, password, "res.country", "search", [[("name", "=", country_name)]]
    )
    return country_ids[0] if country_ids else False


def get_state_id(models, db, uid, password, country_id, state_name):
    """get the state id based on the state name"""
    state_ids = models.execute_kw(
        db,
        uid,
        password,
        "res.country.state",
        "search",
        [[("name", "=", state_name), ("country_id", "=", country_id)]],
    )
    return state_ids[0] if state_ids else False


def get_existing_contacts(models, db, uid, password):
    """get all contacts from odoo"""
    try:
        existing_contacts = models.execute_kw(
            db,
            uid,
            password,
            "res.partner",
            "search_read",
            [[("name", "!=", False), ("email", "!=", False)]],
            {"fields": ["name", "email"]},
        )
        return existing_contacts

    except Exception as e:
        print(f"Erro ao buscar contatos existentes: {e}")
        return []
