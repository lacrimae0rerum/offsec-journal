from fastapi import APIRouter, Depends, HTTPException

from api.auth import require_api_key
from api.core import db, queries
from api.core.coherence import check_person

router = APIRouter(prefix="/people", tags=["people"], dependencies=[Depends(require_api_key)])


@router.get("")
async def list_people(archived: bool = False) -> list[dict]:
    with db.transaction() as conn:
        return queries.list_people(conn, include_archived=archived)


@router.get("/{person_id}")
async def get_person(person_id: str) -> dict:
    with db.transaction() as conn:
        p = queries.get_person(conn, person_id)
        if p is None:
            raise HTTPException(404, f"person {person_id} not found")
        return p


@router.get("/{person_id}/skills")
async def get_person_skills(person_id: str) -> list[dict]:
    with db.transaction() as conn:
        p = queries.get_person(conn, person_id)
        if p is None:
            raise HTTPException(404)
        return p["skills"]


@router.get("/{person_id}/coherence")
async def get_person_coherence(person_id: str) -> dict:
    with db.transaction() as conn:
        p = queries.get_person(conn, person_id)
        if p is None:
            raise HTTPException(404)
        warnings = check_person(p, p["skills"])
        return {"person_id": person_id, "ok": len(warnings) == 0, "warnings": warnings}
