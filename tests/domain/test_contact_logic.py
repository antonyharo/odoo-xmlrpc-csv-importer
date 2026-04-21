import pytest

from src.odoo_xmlrpc_csv_importer.domain.contact import is_duplicate


@pytest.fixture
def set_emails() -> set[str]:
    return {"a@a.com", "b@b.com", "c@c.com"}


@pytest.mark.parametrize(
    "email_input, expected", [("a@a.com", True), ("new@example.com", False)]
)
def test_is_duplicate(set_emails, email_input, expected):
    assert is_duplicate(email_input, set_emails) == expected
