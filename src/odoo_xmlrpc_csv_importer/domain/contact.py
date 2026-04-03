from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator


class ContactSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)

    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    function: str | None = Field(None, max_length=100)
    company_name: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    country_id: str | None = Field(None, max_length=50)
    state_id: str | None = Field(None, max_length=50)
    street: str | None = Field(None, max_length=255)
    website: HttpUrl | None = None

    @field_validator("email")
    @classmethod
    def validate_email_case(cls, v: str):
        return v.lower()


def validate_contact(contact: dict) -> dict:
    validated_contact = ContactSchema(**contact)
    return validated_contact.model_dump(mode="json")


def is_duplicate(email: str, set_emails: set[str]):
    return email in set_emails
