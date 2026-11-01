# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Serialize ``os.fork``/``os.forkpty`` across threads.

filelock >= 3.30 installs a process-wide audit hook that raises
``RuntimeError("os.forkpty is unsafe while filelock is changing descriptor
ownership")`` when one thread forks while another thread is between
filelock's before-fork and after-fork handlers. The broker opens device
connections on parallel executor threads, and Unicon spawns each SSH session
with ``pty.fork()`` -> ``os.forkpty()``, so two concurrent connects can make
one of them fail. Holding a lock around the fork call keeps the forks from
overlapping. ``subprocess`` is unaffected (``fork_exec`` only fails for the
thread's own filelock transition), so it is not wrapped.
"""

import functools
import os
import threading
from collections.abc import Callable
from typing import Any

_FORK_FUNCTIONS = ("fork", "forkpty")
# Marks our wrappers so a repeated install never wraps one again: the lock is
# not reentrant, so a double wrap would deadlock on the first fork.
_GUARD_MARKER = "_nac_test_fork_guard"
_fork_lock = threading.Lock()
_install_lock = threading.Lock()


def _serialized(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with _fork_lock:
            return func(*args, **kwargs)

    setattr(wrapper, _GUARD_MARKER, True)
    return wrapper


def serialize_forks() -> None:
    """Wrap ``os.fork`` and ``os.forkpty`` so only one thread forks at a time.

    Idempotent and a no-op on platforms without these functions (Windows).
    """
    with _install_lock:
        for name in _FORK_FUNCTIONS:
            original = getattr(os, name, None)
            if original is not None and not getattr(original, _GUARD_MARKER, False):
                setattr(os, name, _serialized(original))
