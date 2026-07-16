from __future__ import annotations

import threading

from core.concurrency import DeviceLockRegistry


def test_second_acquire_on_same_key_fails_while_held() -> None:
    registry = DeviceLockRegistry()

    with registry.try_acquire("device-1") as first_acquired:
        assert first_acquired is True
        with registry.try_acquire("device-1") as second_acquired:
            assert second_acquired is False


def test_lock_is_released_after_context_exit() -> None:
    registry = DeviceLockRegistry()

    with registry.try_acquire("device-1") as acquired:
        assert acquired is True

    with registry.try_acquire("device-1") as acquired_again:
        assert acquired_again is True


def test_different_keys_never_block_each_other() -> None:
    registry = DeviceLockRegistry()

    with registry.try_acquire("device-1") as first:
        assert first is True
        with registry.try_acquire("device-2") as second:
            assert second is True


def test_concurrent_threads_only_one_wins_the_same_key() -> None:
    registry = DeviceLockRegistry()
    results: list[bool] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        barrier.wait()
        with registry.try_acquire("device-1") as acquired:
            results.append(acquired)
            if acquired:
                threading.Event().wait(0.05)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == [False, True]
