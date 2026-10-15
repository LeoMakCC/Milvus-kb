from pathlib import Path

from knowledgeqa.instance_lock import InstanceLock


def test_first_lock_can_be_acquired(tmp_path: Path) -> None:
    lock = InstanceLock(tmp_path / "app.lock")

    assert lock.try_acquire() is True
    lock.release()


def test_second_lock_is_rejected_until_first_releases(tmp_path: Path) -> None:
    first = InstanceLock(tmp_path / "app.lock")
    second = InstanceLock(tmp_path / "app.lock")

    assert first.try_acquire() is True
    assert second.try_acquire() is False

    first.release()

    assert second.try_acquire() is True
    second.release()
