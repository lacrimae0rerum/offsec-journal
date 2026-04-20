from fastapi import APIRouter, Depends, HTTPException

from api.auth import require_api_key
from api.core import db, queries

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(require_api_key)])


@router.get("")
async def list_projects(status: str | None = None, archived: bool = False) -> list[dict]:
    with db.transaction() as conn:
        return queries.list_projects(conn, status=status, include_archived=archived)


@router.get("/{code}")
async def get_project(code: str) -> dict:
    with db.transaction() as conn:
        p = queries.get_project(conn, code)
        if p is None:
            raise HTTPException(404, f"project {code} not found")
        return p
