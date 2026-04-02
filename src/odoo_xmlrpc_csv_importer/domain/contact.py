from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator


class ContactSchema(BaseModel):
    name: str = Field(max_length=100)
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
    def serialize_website(cls, v: str):
        return v.lower()
