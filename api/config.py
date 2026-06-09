"""Runtime configuration loaded from environment/.env.

`make install` generates .env. The app doesn't own auth secrets anymore —
Authelia is the authentication perimeter; the only auth-adjacent setting here
is `trusted_proxy_ips`, the whitelist of IPs allowed to present Remote-User.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Auth / trust
    trusted_proxy_ips: str = "127.0.0.1"  # CSV. IPs allowed as request.client.host
    # Optional. The journal does not manage login/logout — that belongs to
    # whatever fronts it (e.g. Authelia at the lab perimeter). Leave empty and
    # the frontend hides the "log out" affordance. Set it via env only if a
    # given deployment really has a logout URL to send users to.
    authelia_logout_url: str = ""

    # Single-tenant mode: auto-provision unknown Authelia users to default team
    single_tenant_mode: bool = False
    single_tenant_default_team: str = "offsec"
    # Role assigned to auto-provisioned users. Default 'member' (safe). Set to
    # 'admin' only if Authelia itself gates access tightly (e.g. small team).
    single_tenant_default_role: str = "member"

    # Dev mode: bypass Authelia + trusted-proxy check entirely.
    # If set, every request is treated as authenticated under this username.
    # Never set in production. Startup aborts if dev_user is set together with
    # a non-loopback api_host (see api/main.py).
    dev_user: str | None = None
    # Explicit opt-in to bind dev_user mode on a LAN address. Required to
    # bypass the loopback safety assert. ONLY use on trusted networks (home
    # WiFi). Anyone reachable can authenticate as dev_user without a password.
    dev_allow_lan: bool = False

    # App
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # LLM (future; not wired in V1)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # Paths
    data_dir: Path = ROOT / "data"
    notes_dir: Path = ROOT / "notes"
    db_path: Path = ROOT / "data" / "cache.db"
    log_dir: Path = ROOT / "logs"

    @property
    def trusted_proxy_ips_list(self) -> list[str]:
        return [ip.strip() for ip in self.trusted_proxy_ips.split(",") if ip.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
