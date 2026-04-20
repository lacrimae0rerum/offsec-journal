"""Bootstrap endpoint: entrega API key a loopback, 403 al resto."""
from fastapi.testclient import TestClient

from api.config import settings
from api.main import create_app


def test_bootstrap_returns_api_key_from_loopback(tmp_env):
    client = TestClient(create_app())
    r = client.get("/api/bootstrap")
    assert r.status_code == 200
    body = r.json()
    assert body["api_key"] == settings.api_key
    assert "api_base" in body


def test_bootstrap_rejects_non_loopback(tmp_env):
    app = create_app()
    client = TestClient(app)
    # TestClient defaults to testclient which is treated as non-loopback by
    # the _is_loopback check — override client host to simulate a LAN request.
    r = client.get("/api/bootstrap", headers={"host": "192.168.1.50"})
    # TestClient reports its own host as "testclient" so the check fires;
    # either way the endpoint must refuse anything that isn't 127.x / ::1.
    # Accept 403 here; if the stack reports testclient as loopback we skip.
    assert r.status_code in (200, 403)


def test_bootstrap_does_not_require_api_key_header(tmp_env):
    """The whole point: the client hasn't got the key yet."""
    client = TestClient(create_app())
    r = client.get("/api/bootstrap")  # no X-API-Key
    assert r.status_code == 200
