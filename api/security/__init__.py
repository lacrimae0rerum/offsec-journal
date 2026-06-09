"""Auth / audit / authorization for requests behind nginx + Authelia.

Public surface:
    from api.security import AuthContext, require_authelia, require_admin

Only these names are stable. Everything else is an implementation detail.
"""
from api.security.audit import (
    client_ip_from_request,
    log_event,
    user_agent_from_request,
)
from api.security.authelia import (
    AuthContext,
    get_user_by_username,
    require_admin,
    require_authelia,
    touch_last_seen,
)

__all__ = [
    "AuthContext",
    "require_authelia",
    "require_admin",
    "get_user_by_username",
    "touch_last_seen",
    "log_event",
    "client_ip_from_request",
    "user_agent_from_request",
]
