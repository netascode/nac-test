# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for ConnectionManager integration with connection_utils.

This module is intentionally minimal. The ConnectionManager's behavior is
validated through e2e tests that establish real connections and
functional tests in the PyATS execution pipeline.
"""

import pytest

from nac_test.pyats_core.ssh.connection_manager import DeviceConnectionManager


class TestConnectionManagerEnvVar:
    """Tests for NAC_TEST_PYATS_MAX_SSH_CONNECTIONS environment variable."""

    def test_connection_manager_respects_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify manager passes correct env_var to calculate_connection_capacity."""
        monkeypatch.setenv("NAC_TEST_PYATS_MAX_SSH_CONNECTIONS", "123456")

        manager = DeviceConnectionManager()

        assert manager.max_concurrent == 123456
