import asyncio

import httpx

from knowledgeqa.api.app import create_app
from knowledgeqa.api.auth import AuthGuard
from knowledgeqa.config import AppPaths, Settings
from knowledgeqa.repository import Repository
from knowledgeqa.security.passwords import hash_password
from knowledgeqa.security.sessions import SessionManager


async def request(app, method: str, path: str, client_ip="127.0.0.1", **kwargs):
    transport = httpx.ASGITransport(app=app, client=(client_ip, 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def make_app(portable_root, repository, sessions):
    return create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=lambda: {"milvus": "disconnected"},
        repository=repository,
        auth_guard=AuthGuard(repository, sessions),
    )


def test_lan_disabled_allows_remote_request(portable_root) -> None:
    repository = Repository(portable_root / "meta.db")
    repository.initialize()
    app = make_app(portable_root, repository, SessionManager())

    response = asyncio.run(
        request(app, "GET", "/api/v1/kbs", client_ip="1.2.3.4")
    )

    assert response.status_code == 200


def test_lan_enabled_requires_login_for_remote_clients(portable_root) -> None:
    repository = Repository(portable_root / "meta.db")
    repository.initialize()
    repository.set_setting("lan_enabled", "1")
    repository.set_setting(
        "shared_password_hash",
        hash_password("secret"),
    )
    app = make_app(portable_root, repository, SessionManager())

    blocked = asyncio.run(
        request(app, "GET", "/api/v1/kbs", client_ip="1.2.3.4")
    )
    wrong = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/auth/login",
            client_ip="1.2.3.4",
            json={"password": "wrong"},
        )
    )
    login = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/auth/login",
            client_ip="1.2.3.4",
            json={"password": "secret"},
        )
    )
    token = login.json()["token"]
    allowed = asyncio.run(
        request(
            app,
            "GET",
            "/api/v1/kbs",
            client_ip="1.2.3.4",
            headers={"Authorization": f"Bearer {token}"},
        )
    )

    assert blocked.status_code == 401
    assert wrong.status_code == 401
    assert login.status_code == 200
    assert allowed.status_code == 200


def test_local_client_bypasses_lan_login(portable_root) -> None:
    repository = Repository(portable_root / "meta.db")
    repository.initialize()
    repository.set_setting("lan_enabled", "1")
    app = make_app(portable_root, repository, SessionManager())

    response = asyncio.run(request(app, "GET", "/api/v1/kbs"))

    assert response.status_code == 200
