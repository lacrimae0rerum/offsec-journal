from fastapi import APIRouter

from api import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "version": __version__}
