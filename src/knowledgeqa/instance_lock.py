from __future__ import annotations

from pathlib import Path

import portalocker


class InstanceLock:
    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        self._file = None

    def try_acquire(self) -> bool:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        file = self._lock_path.open("a+", encoding="utf-8")
        try:
            portalocker.lock(file, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.exceptions.LockException:
            file.close()
            return False
        self._file = file
        return True

    def release(self) -> None:
        if self._file is None:
            return
        portalocker.unlock(self._file)
        self._file.close()
        self._file = None
