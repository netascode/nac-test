# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for CommandCache thread-safety and correctness."""

import threading
import time
from typing import Any

from nac_test.pyats_core.ssh.command_cache import CommandCache


class TestCommandCacheBasic:
    """Basic get/set/clear correctness."""

    def test_get_returns_none_on_miss(self) -> None:
        """Unset key returns None."""
        cache = CommandCache("router-1")
        assert cache.get("show version") is None

    def test_set_and_get(self) -> None:
        """Value set is returned by get."""
        cache = CommandCache("router-1")
        cache.set("show version", "output text")
        assert cache.get("show version") == "output text"

    def test_get_returns_none_after_expiry(self) -> None:
        """Entry is treated as expired once TTL passes."""
        cache = CommandCache("router-1", ttl=1)
        cache.set("show version", "stale output")
        time.sleep(1.1)
        assert cache.get("show version") is None

    def test_clear_removes_all_entries(self) -> None:
        """clear() purges all cached entries."""
        cache = CommandCache("router-1")
        cache.set("show version", "v1")
        cache.set("show ip route", "r1")
        cache.clear()
        assert cache.get("show version") is None
        assert cache.get("show ip route") is None

    def test_get_cache_stats_counts(self) -> None:
        """get_cache_stats returns correct valid/expired/total counts."""
        cache = CommandCache("router-1", ttl=1)
        cache.set("cmd-a", "out-a")
        cache.set("cmd-b", "out-b")
        stats = cache.get_cache_stats()
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert stats["expired_entries"] == 0

    def test_get_cache_stats_after_expiry(self) -> None:
        """get_cache_stats counts expired entries correctly."""
        cache = CommandCache("router-1", ttl=1)
        cache.set("cmd-a", "out-a")
        time.sleep(1.1)
        cache.set("cmd-b", "out-b")  # added after expiry; still valid
        stats = cache.get_cache_stats()
        assert stats["expired_entries"] == 1
        assert stats["valid_entries"] == 1
        assert stats["total_entries"] == 2


class TestCommandCacheConcurrency:
    """Verify CommandCache is safe under concurrent get/set from multiple threads.

    CommandCache uses threading.Lock for all mutating operations.  These tests
    drive the lock under real contention to surface data races that a sequential
    test cannot detect.

    CPython GIL note: due to the GIL, simple dict mutations are effectively atomic
    in CPython, so these tests will not *fail* if the lock is removed — the GIL
    masks the race.  The tests are kept for two reasons: (1) they serve as smoke
    tests for general thread-safe behaviour; (2) they will catch real races under
    free-threaded Python (PEP 703 / Python 3.13+) where the GIL is optional.
    The lock is still correct and necessary for the compound check-read-delete
    sequence in get() and for forward compatibility.
    """

    def test_concurrent_get_set_no_exceptions(self) -> None:
        """Hammering get/set from multiple threads raises no exceptions and leaves
        the cache in a consistent state.

        10 writer threads and 10 reader threads operate concurrently on 5 commands,
        each performing 100 iterations.  The test asserts:
        - No thread raised an exception (lock protects against dict mutation races).
        - Every value returned by get() is either None (pre-write race) or the exact
          string that was written — never a partially-constructed value.

        Note: see class docstring for the CPython GIL caveat.
        """
        cache = CommandCache("concurrent-test", ttl=3600)
        errors: list[Exception] = []
        bad_values: list[Any] = []
        errors_lock = threading.Lock()

        commands = [f"show interface {i}" for i in range(5)]
        expected = {cmd: f"output for {cmd}" for cmd in commands}

        def writer(cmd: str) -> None:
            for _ in range(100):
                try:
                    cache.set(cmd, expected[cmd])
                except Exception as exc:
                    with errors_lock:
                        errors.append(exc)

        def reader(cmd: str) -> None:
            for _ in range(100):
                try:
                    result = cache.get(cmd)
                    # Must be None (not yet written) or the exact expected string.
                    if result is not None and result != expected[cmd]:
                        with errors_lock:
                            bad_values.append((cmd, result))
                except Exception as exc:
                    with errors_lock:
                        errors.append(exc)

        threads = [threading.Thread(target=writer, args=(cmd,)) for cmd in commands] + [
            threading.Thread(target=reader, args=(cmd,)) for cmd in commands
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Threads raised exceptions: {errors}"
        assert bad_values == [], f"get() returned unexpected values: {bad_values}"

    def test_concurrent_get_cache_stats_no_exceptions(self) -> None:
        """get_cache_stats() can be called safely while writers race against it.

        A writer thread continuously sets entries while the main thread calls
        get_cache_stats() repeatedly.  No exception should be raised and the
        returned counts must be internally consistent (valid + expired == total).

        Note: see class docstring for the CPython GIL caveat.
        """
        cache = CommandCache("stats-test", ttl=3600)
        stop_event = threading.Event()
        stats_errors: list[Exception] = []

        def continuous_writer() -> None:
            i = 0
            while not stop_event.is_set():
                cache.set(f"cmd-{i % 20}", f"output-{i}")
                i += 1

        writer_thread = threading.Thread(target=continuous_writer)
        writer_thread.start()

        try:
            for _ in range(200):
                try:
                    stats = cache.get_cache_stats()
                    assert (
                        stats["valid_entries"] + stats["expired_entries"]
                        == stats["total_entries"]
                    )
                except Exception as exc:
                    stats_errors.append(exc)
        finally:
            stop_event.set()
            writer_thread.join()

        assert stats_errors == [], f"get_cache_stats() raised: {stats_errors}"
