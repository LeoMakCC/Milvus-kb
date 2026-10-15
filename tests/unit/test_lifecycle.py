from knowledgeqa.lifecycle import ExitChoice, ExitCoordinator, ExitDecision


def test_exit_without_jobs_exits_immediately() -> None:
    coordinator = ExitCoordinator(jobs_running=lambda: 0)

    assert coordinator.decide(choice_provider=lambda: ExitChoice.CANCEL) == ExitDecision.EXIT


def test_exit_with_jobs_can_keep_running() -> None:
    coordinator = ExitCoordinator(jobs_running=lambda: 1)

    assert coordinator.decide(choice_provider=lambda: ExitChoice.KEEP_RUNNING) == ExitDecision.KEEP_RUNNING


def test_exit_with_jobs_can_stop_and_exit() -> None:
    coordinator = ExitCoordinator(jobs_running=lambda: 1)

    assert coordinator.decide(choice_provider=lambda: ExitChoice.STOP_AND_EXIT) == ExitDecision.STOP_AND_EXIT


def test_exit_with_jobs_can_cancel_exit() -> None:
    coordinator = ExitCoordinator(jobs_running=lambda: 1)

    assert coordinator.decide(choice_provider=lambda: ExitChoice.CANCEL) == ExitDecision.CANCEL_EXIT
