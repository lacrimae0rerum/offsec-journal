from pydantic import BaseModel, Field


class Office(BaseModel):
    office_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    city: str
    country: str = ""
    lat: float = 0.0
    lon: float = 0.0
    archived: bool = False
