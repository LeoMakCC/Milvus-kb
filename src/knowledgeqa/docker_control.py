from __future__ import annotations

import subprocess
from pathlib import Path


class DockerController:
    def __init__(
        self,
        compose_file: Path,
        project_name: str = "knowledgeqa",
        runner=subprocess.run,
    ) -> None:
        self._compose_file = compose_file
        self._project_name = project_name
        self._runner = runner

    def _run(self, args: list[str], timeout: int = 60):
        return self._runner(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def is_available(self) -> bool:
        return self._run(["docker", "version"], timeout=10).returncode == 0

    def is_running(self) -> bool:
        return self._run(["docker", "info"], timeout=10).returncode == 0

    def compose_up(self):
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

    def compose_down(self):
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
