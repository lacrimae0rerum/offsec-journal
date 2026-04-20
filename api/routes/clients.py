from fastapi import APIRouter, Depends, HTTPException

from api.auth import require_api_key
from api.core import db, queries

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(require_api_key)])


@router.get("")
async def list_clients(archived: bool = False) -> list[dict]:
    with db.transaction() as conn:
        return queries.list_clients(conn, include_archived=archived)


@router.get("/{client_id}")
async def get_client(client_id: str) -> dict:
    with db.transaction() as conn:
        clients = queries.list_clients(conn, include_archived=True)
        c = next((x for x in clients if x["id"] == client_id), None)
        if c is None:
            raise HTTPException(404, f"client {client_id} not found")
        return c
