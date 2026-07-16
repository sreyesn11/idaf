from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

import streamlit as st


class DeviceLockRegistry:
    """Non-blocking per-device guard.

    Prevents two diagnostics/commands from running concurrently against the
    same device (which could overload a single router), without introducing
    a job queue: if the lock is already held, `try_acquire` yields False and
    the caller should skip the run with a friendly message instead of
    waiting.
    """

    def __init__(self) -> None:
        self._registry_lock = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    @contextmanager
    def try_acquire(self, device_key: str) -> Iterator[bool]:
        with self._registry_lock:
            lock = self._locks.setdefault(device_key, threading.Lock())
        acquired = lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                lock.release()


@st.cache_resource
def get_device_lock_registry() -> DeviceLockRegistry:
    return DeviceLockRegistry()
