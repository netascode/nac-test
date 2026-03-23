# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for PyATSOrchestrator environment variable handling."""

import pytest

from nac_test.pyats_core.orchestrator import PyATSOrchestrator

from .conftest import PyATSTestDirs


class TestOrchestratorEnvVarProcesses:
    """Tests for NAC_TEST_PYATS_PROCESSES environment variable in orchestrator."""

    def test_orchestrator_respects_nac_test_pyats_processes_env_var(
        self,
        pyats_test_dirs: PyATSTestDirs,
        aci_controller_env: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify orchestrator passes correct env_var to calculate_worker_capacity."""
        monkeypatch.setenv("NAC_TEST_PYATS_PROCESSES", "123456")

        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.test_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            controller_type="ACI",
        )

        assert orchestrator.max_workers == 123456
