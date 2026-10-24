from __future__ import annotations

import subprocess
import time
from pathlib import Path

from knowledgeqa.process_utils import hidden_window_kwargs


class DockerController:
    def __init__(
        self,
        compose_file: Path,
        project_name: str = "knowledgeqa",
        runner=subprocess.run,
        clock=time.monotonic,
        probe_cache_seconds: float = 5.0,
    ) -> None:
        self._compose_file = compose_file
        self._project_name = project_name
        self._runner = runner
        self._clock = clock
        self._probe_cache_seconds = probe_cache_seconds
        self._probe_cache: dict[str, tuple[float, bool]] = {}

    def _run(self, args: list[str], timeout: int = 60):
        return self._runner(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            **hidden_window_kwargs(),
        )

    def invalidate_status(self) -> None:
        self._probe_cache.clear()

    def _probe(self, key: str, args: list[str], timeout: int) -> bool:
        cached = self._probe_cache.get(key)
        now = self._clock()
        if cached is not None and now - cached[0] < self._probe_cache_seconds:
            return cached[1]
        value = self._run(args, timeout=timeout).returncode == 0
        self._probe_cache[key] = (now, value)
        return value

    def is_available(self) -> bool:
        return self._probe("available", ["docker", "version"], timeout=10)

    def is_running(self) -> bool:
        return self._probe("running", ["docker", "info"], timeout=10)

    def compose_up(self):
        try:
            return self._run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(self._compose_file),
                    "-p",
                    self._project_name,
                    "up",
                    "-d",
                ]
            )
        finally:
            self.invalidate_status()

    def compose_down(self):
        try:
            return self._run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(self._compose_file),
                    "-p",
                    self._project_name,
                    "down",
                ]
            )
        finally:
            self.invalidate_status()

    def compose_ps(self):
        return self._run(
            [
                "docker",
                "compose",
                "-f",
                str(self._compose_file),
                "-p",
                self._project_name,
                "ps",
            ]
        )
