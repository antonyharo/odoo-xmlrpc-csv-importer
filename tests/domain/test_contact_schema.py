import pytest
from pydantic import ValidationError

from src.odoo_xmlrpc_csv_importer.domain.contact import validate_contact


@pytest.mark.parametrize(
    "input_patch, output_patch",
    [
        (
            {},
            {},
        ),
        (
            {"email": "JOHNDOE@EXAMPLE.COM"},
            {"email": "johndoe@example.com"},
        ),
        (
            {
                "extra_field": "ignore",
            },
            {},
        ),
    ],
)
def test_validate_contact_success(base_contact, input_patch, output_patch):
    full_input = base_contact | input_patch
    full_output = base_contact | output_patch
    assert validate_contact(full_input) == full_output


@pytest.mark.parametrize(
    "input_patch",
    [
        ({"website": "not-a-website"}),
        ({"email": "not-an-email"}),
        ({"name": ""}),
        ({"email": ""}),
    ],
)
def test_validate_contact_error(base_contact, input_patch):
    full_input = base_contact | input_patch

    with pytest.raises(ValidationError):
        validate_contact(full_input)
