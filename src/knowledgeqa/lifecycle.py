from __future__ import annotations

from collections.abc import Callable
from enum import Enum


class ExitChoice(str, Enum):
    KEEP_RUNNING = "keep_running"
    STOP_AND_EXIT = "stop_and_exit"
    CANCEL = "cancel"


class ExitDecision(str, Enum):
    EXIT = "exit"
    KEEP_RUNNING = "keep_running"
    STOP_AND_EXIT = "stop_and_exit"
    CANCEL_EXIT = "cancel_exit"


class ExitCoordinator:
    def __init__(self, jobs_running: Callable[[], int]) -> None:
        self._jobs_running = jobs_running

    def decide(self, choice_provider: Callable[[], ExitChoice]) -> ExitDecision:
        if self._jobs_running() == 0:
            return ExitDecision.EXIT

        choice = ExitChoice(choice_provider())
        if choice is ExitChoice.KEEP_RUNNING:
            return ExitDecision.KEEP_RUNNING
        if choice is ExitChoice.STOP_AND_EXIT:
            return ExitDecision.STOP_AND_EXIT
        return ExitDecision.CANCEL_EXIT
