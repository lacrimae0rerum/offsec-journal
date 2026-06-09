from pydantic import BaseModel, Field


class Skill(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label_es: str
    description: str = "TODO: operator-defined"
    archived: bool = False
