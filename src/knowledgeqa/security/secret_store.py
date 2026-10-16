from __future__ import annotations

import sys


class WindowsSecretStore:
    def _crypt(self):
        if sys.platform != "win32":
            raise RuntimeError("Windows DPAPI is only available on Windows")
        import win32crypt

        return win32crypt

    def protect(self, value: str) -> bytes:
        crypt = self._crypt()
        return crypt.CryptProtectData(
            value.encode("utf-8"),
            "KnowledgeQA",
            None,
            None,
            None,
            0,
        )

    def unprotect(self, value: bytes) -> str:
        crypt = self._crypt()
        _description, plain = crypt.CryptUnprotectData(
            value,
            None,
            None,
            None,
            0,
        )
        return plain.decode("utf-8")
