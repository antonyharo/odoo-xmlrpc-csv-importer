import pytest


@pytest.fixture
def base_contact() -> dict:
    return {
        "name": "John Doe",
        "email": "johndoe@example.com",
        "function": None,
        "company_name": None,
        "city": None,
        "country_id": None,
        "state_id": None,
        "street": None,
        "website": None,
    }
