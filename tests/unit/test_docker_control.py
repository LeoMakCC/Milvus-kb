import sys
from pathlib import Path
from subprocess import CompletedProcess

from knowledgeqa.docker_control import DockerController


class FakeRunner:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.calls = []
        self.kwargs = []

    def __call__(self, args, capture_output, text, timeout, **kwargs):
        self.calls.append(args)
        self.kwargs.append(kwargs)
        return CompletedProcess(args, self.returncode, stdout="ok", stderr="")


def test_docker_available_uses_version_command(tmp_path: Path) -> None:
    runner = FakeRunner()
    controller = DockerController(tmp_path / "docker-compose.yml", runner=runner)

    assert controller.is_available() is True
    assert runner.calls[0][:2] == ["docker", "version"]


def test_compose_up_uses_project_name_and_file(tmp_path: Path) -> None:
    runner = FakeRunner()
    compose = tmp_path / "docker-compose.yml"
    controller = DockerController(compose, runner=runner)

    result = controller.compose_up()

    assert result.returncode == 0
    assert runner.calls[0] == [
        "docker",
        "compose",
        "-f",
        str(compose),
        "-p",
        "knowledgeqa",
        "up",
        "-d",
    ]


def test_subprocess_runs_without_console_window(tmp_path: Path) -> None:
    runner = FakeRunner()
    controller = DockerController(tmp_path / "docker-compose.yml", runner=runner)

    controller.is_available()

    kwargs = runner.kwargs[0]
    if sys.platform == "win32":
        assert kwargs["creationflags"] & 0x08000000
        assert kwargs["startupinfo"].wShowWindow == 0
    else:
        assert kwargs == {}


def test_status_probe_is_cached(tmp_path: Path) -> None:
    runner = FakeRunner()
    now = [100.0]
    controller = DockerController(
        tmp_path / "docker-compose.yml",
        runner=runner,
        clock=lambda: now[0],
        probe_cache_seconds=5.0,
    )

    assert controller.is_available() is True
    assert controller.is_available() is True
    assert len(runner.calls) == 1

    now[0] += 6
    assert controller.is_available() is True
    assert len(runner.calls) == 2


def test_compose_down_invalidates_probe_cache(tmp_path: Path) -> None:
    runner = FakeRunner()
    controller = DockerController(tmp_path / "docker-compose.yml", runner=runner)

    controller.is_available()
    controller.compose_down()
    controller.is_available()

    assert [call[:2] for call in runner.calls] == [
        ["docker", "version"],
        ["docker", "compose"],
        ["docker", "version"],
    ]
