from pydantic import BaseModel, EmailStr, HttpUrl

class ContactSchema(BaseModel):
    name: str
    email: EmailStr
    function: str | None
    company_name: str | None
    city: str | None
    country_id: str | None
    state_id: str | None
    street: str | None
    website: HttpUrl | None