from knowledgeqa.security.passwords import hash_password, verify_password
from knowledgeqa.security.sessions import SessionManager


def test_password_hash_and_verify() -> None:
    hashed = hash_password("secret")

    assert hashed != "secret"
    assert verify_password("secret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_session_manager_create_validate_and_revoke() -> None:
    sessions = SessionManager(ttl_seconds=60)

    token = sessions.create()

    assert sessions.validate(token) is True
    sessions.revoke(token)
    assert sessions.validate(token) is False


def test_session_manager_expires_tokens() -> None:
    now = [100.0]
    sessions = SessionManager(ttl_seconds=10, clock=lambda: now[0])
    token = sessions.create()

    now[0] = 111.0

    assert sessions.validate(token) is False
