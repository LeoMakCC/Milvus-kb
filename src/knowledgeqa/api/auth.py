from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from knowledgeqa.security.passwords import verify_password

PUBLIC_PATHS = {
    "/api/v1/health",
    "/api/v1/auth/login",
}


class LoginRequest(BaseModel):
    password: str


class AuthGuard:
    def __init__(self, repository, sessions) -> None:
        self._repository = repository
        self._sessions = sessions

    def lan_enabled(self) -> bool:
        return self._repository.get_setting("lan_enabled", "0") == "1"

    def password_hash(self) -> str:
        return self._repository.get_setting("shared_password_hash", "") or ""

    @staticmethod
    def is_local(request: Request) -> bool:
        host = request.client.host if request.client else ""
        return host in {"127.0.0.1", "::1", "localhost"}

    @staticmethod
    def bearer_token(request: Request) -> str | None:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return header[7:].strip()
        return None

    def is_public(self, path: str) -> bool:
        return (
            path in PUBLIC_PATHS
            or path == "/"
            or path.startswith("/static/")
            or path.startswith("/docs")
            or path.startswith("/openapi.json")
        )

    def is_allowed(self, request: Request) -> bool:
        if not self.lan_enabled():
            return True
        if self.is_public(request.url.path):
            return True
        if self.is_local(request):
            return True
        return self._sessions.validate(self.bearer_token(request))

    def authenticate(self, password: str) -> str | None:
        encoded = self.password_hash()
        if not encoded or not verify_password(password, encoded):
            return None
        return self._sessions.create()


def create_auth_router(auth_guard: AuthGuard) -> APIRouter:
    router = APIRouter(prefix="/api/v1/auth")

    @router.post("/login")
    def login(request: LoginRequest):
        token = auth_guard.authenticate(request.password)
        if token is None:
            raise HTTPException(401, "Invalid password")
        return {"token": token}

    @router.post("/logout")
    def logout(request: Request):
        token = auth_guard.bearer_token(request)
        if token:
            auth_guard._sessions.revoke(token)
        return {"ok": True}

    @router.get("/session")
    def session(request: Request):
        if auth_guard.is_allowed(request):
            return {"authenticated": True}
        raise HTTPException(401, "Authentication required")

    return router


async def auth_middleware(request: Request, call_next, auth_guard: AuthGuard):
    if not auth_guard.is_allowed(request):
        return JSONResponse(
            {"detail": "Authentication required"},
            status_code=401,
        )
    return await call_next(request)
