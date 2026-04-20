"""Bootstrap endpoint — entrega la API key al frontend cuando llega desde loopback.

El producto corre en red local del MSSP (prompt original): 2 usuarios confiables,
backend + frontend en la misma máquina. Forzar copy-paste manual de la key es
fricción pura. Este endpoint solo responde a `127.0.0.1` / `::1` / `localhost`,
cualquier otro origen recibe 403 — es una salvaguarda mínima pero suficiente
para el deploy en LAN. Si mañana el backend se expone a internet, quitar este
endpoint es trivial.
"""
from fastapi import APIRouter, HTTPException, Request

from api.config import settings

router = APIRouter(tags=["bootstrap"])

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def _is_loopback(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    # IPv6-mapped IPv4: ::ffff:127.0.0.1
    if host.startswith("::ffff:"):
        host = host.split("::ffff:", 1)[1]
    return host in LOOPBACK_HOSTS


@router.get("/bootstrap")
async def bootstrap(request: Request) -> dict:
    if not _is_loopback(request):
        raise HTTPException(403, "bootstrap only available from loopback")
    return {"api_key": settings.api_key, "api_base": ""}
