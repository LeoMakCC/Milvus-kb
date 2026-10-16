from knowledgeqa.security.secret_store import WindowsSecretStore


def test_secret_round_trip() -> None:
    store = WindowsSecretStore()

    protected = store.protect("sk-test")

    assert protected != b"sk-test"
    assert store.unprotect(protected) == "sk-test"
