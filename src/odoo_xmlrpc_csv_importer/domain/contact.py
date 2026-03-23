from pydantic import BaseModel, EmailStr

class Contact(BaseModel):
    name: str
    email: EmailStr
    function: str | None = None
    company_name: str | None = None
    city: str
    country_id: str
    state_id: str
    street: str
    website: str |
