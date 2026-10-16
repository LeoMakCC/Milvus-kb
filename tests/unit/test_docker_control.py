from pathlib import Path
from subprocess import CompletedProcess

from knowledgeqa.docker_control import DockerController


class FakeRunner:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.calls = []

    def __call__(self, args, capture_output, text, timeout):
        self.calls.append(args)
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
