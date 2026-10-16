from __future__ import annotations

import secrets
import time
from collections.abc import Callable


class SessionManager:
    def __init__(
        self,
        ttl_seconds: int = 86400,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._sessions: dict[str, float] = {}

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = self._clock() + self._ttl_seconds
        return token

    def validate(self, token: str | None) -> bool:
        if not token:
            return False
        expires_at = self._sessions.get(token)
        if expires_at is None:
            return False
        if self._clock() >= expires_at:
            self._sessions.pop(token, None)
            return False
        return True

    def revoke(self, token: str) -> None:
        self._sessions.pop(token, None)
