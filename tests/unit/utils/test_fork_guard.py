# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for the fork serialization guard."""

import os
import sys
import threading
from collections.abc import Iterator

import pytest

import nac_test.utils.fork_guard as fork_guard

pytestmark = [
    pytest.mark.skipif(not hasattr(os, "forkpty"), reason="os.forkpty is POSIX-only"),
    # Forking from a multi-threaded process is exactly what these tests do.
    pytest.mark.filterwarnings("ignore:This process .* is multi-threaded"),
]


@pytest.fixture
def fresh_guard(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Start each test unguarded, then restore whatever was installed before.

    Another test in this worker (e.g. a CLI run) may already have installed
    the guard, so unwrap to the real functions rather than reusing them.
    """
    for name in ("fork", "forkpty"):
        current = getattr(os, name)
        monkeypatch.setattr(os, name, getattr(current, "__wrapped__", current))
    yield


def _concurrent_forkpty_errors(threads: int = 4, forks_per_thread: int = 50) -> int:
    """Fork from several threads at once and count the RuntimeErrors raised."""
    import filelock  # noqa: F401  # importing installs filelock's fork audit hook

    errors: list[RuntimeError] = []

    def spawn() -> None:
        for _ in range(forks_per_thread):
            try:
                pid, fd = os.forkpty()
            except RuntimeError as e:
                errors.append(e)
                continue
            if pid == 0:
                os._exit(0)
            os.waitpid(pid, 0)
            os.close(fd)

    switch_interval = sys.getswitchinterval()
    # Switch threads as often as possible so forks overlap reliably.
    sys.setswitchinterval(1e-6)
    try:
        workers = [threading.Thread(target=spawn) for _ in range(threads)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
    finally:
        sys.setswitchinterval(switch_interval)
    return len(errors)


class TestSerializeForks:
    """Tests for serialize_forks."""

    def test_wraps_fork_functions(self, fresh_guard: None) -> None:
        original_fork, original_forkpty = os.fork, os.forkpty

        fork_guard.serialize_forks()

        assert os.fork is not original_fork
        assert os.forkpty is not original_forkpty
        assert os.fork.__wrapped__ is original_fork  # type: ignore[attr-defined]
        assert os.forkpty.__wrapped__ is original_forkpty  # type: ignore[attr-defined]

    def test_is_idempotent(self, fresh_guard: None) -> None:
        original_forkpty = os.forkpty
        fork_guard.serialize_forks()
        wrapped_forkpty = os.forkpty

        fork_guard.serialize_forks()

        assert os.forkpty is wrapped_forkpty
        # A double wrap would take the non-reentrant lock twice and hang.
        assert os.forkpty.__wrapped__ is original_forkpty  # type: ignore[attr-defined]

    def test_concurrent_forkpty_does_not_raise(self, fresh_guard: None) -> None:
        # Control run: without the guard the race must show up, otherwise this
        # environment (e.g. Python < 3.12, where filelock skips its audit hook)
        # cannot tell whether the guard works.
        if _concurrent_forkpty_errors() == 0:
            pytest.skip("concurrent forkpty does not fail here without the guard")

        fork_guard.serialize_forks()

        assert _concurrent_forkpty_errors() == 0
