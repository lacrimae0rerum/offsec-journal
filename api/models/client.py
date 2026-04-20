from typing import Literal

from pydantic import BaseModel, Field

ClientStatus = Literal["activo", "archivado", "prospect"]


class Contact(BaseModel):
    name: str
    role: str = ""
    email: str = ""
    phone: str = ""


class Client(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    sector: str = ""
    size: str = ""
    country: str = ""
    status: ClientStatus = "activo"
    description: str = ""
    archived: bool = False
    contacts: list[Contact] = []
