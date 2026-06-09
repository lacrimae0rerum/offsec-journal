from typing import Any
from fastapi import APIRouter

from api import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "version": __version__}
