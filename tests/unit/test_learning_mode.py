# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for the learning mode framework.

Tests cover:
- LearningModeMixin behavior (mode detection, property access)
- Learned state file utilities (save/load)
- CLI flag recognition
- Environment variable propagation
"""

import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from nac_test.pyats_core.common.learning_mode_mixin import LearningModeMixin
from nac_test.utils.learned_state import load_learned_state, save_learned_state


class TestLearningModeMixin:
    """Tests for the LearningModeMixin class."""

    def _make_instance(self) -> LearningModeMixin:
        """Create a bare mixin instance for testing."""
        return LearningModeMixin()

    def test_supports_learning_class_attribute(self) -> None:
        """SUPPORTS_LEARNING is True by default on the mixin."""
        instance = self._make_instance()
        assert instance.SUPPORTS_LEARNING is True

    def test_is_learn_mode_false_by_default(self) -> None:
        """is_learn_mode returns False when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NAC_TEST_LEARN", None)
            instance = self._make_instance()
            assert instance.is_learn_mode is False

    def test_is_learn_mode_true_when_set(self) -> None:
        """is_learn_mode returns True when NAC_TEST_LEARN is set."""
        with patch.dict(os.environ, {"NAC_TEST_LEARN": "1"}):
            instance = self._make_instance()
            assert instance.is_learn_mode is True

    def test_is_learn_mode_false_for_empty_string(self) -> None:
        """is_learn_mode returns False for empty string."""
        with patch.dict(os.environ, {"NAC_TEST_LEARN": ""}):
            instance = self._make_instance()
            assert instance.is_learn_mode is False

    def test_learned_state_dir_default(self) -> None:
        """learned_state_dir returns default path when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NAC_TEST_LEARNED_STATE_DIR", None)
            instance = self._make_instance()
            assert instance.learned_state_dir == Path("learned_state")

    def test_learned_state_dir_from_env(self) -> None:
        """learned_state_dir reads from NAC_TEST_LEARNED_STATE_DIR."""
        with patch.dict(os.environ, {"NAC_TEST_LEARNED_STATE_DIR": "/tmp/my_learned"}):
            instance = self._make_instance()
            assert instance.learned_state_dir == Path("/tmp/my_learned")

    def test_capture_learned_state_raises_not_implemented(self) -> None:
        """Default capture_learned_state raises NotImplementedError."""
        import asyncio

        instance = self._make_instance()
        with pytest.raises(NotImplementedError, match="SUPPORTS_LEARNING=True"):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    instance.capture_learned_state(
                        asyncio.Semaphore(1), None, [{"item": "test"}]
                    )
                )
            finally:
                loop.close()


class TestLearnedStateUtilities:
    """Tests for the learned_state save/load utility functions."""

    def test_save_learned_state_creates_file(self, tmp_path: Path) -> None:
        """save_learned_state writes a YAML file to the output directory."""
        data: dict[str, Any] = {"sdwan": {"sites": [{"id": 100}]}}
        result = save_learned_state(data, tmp_path, "VerifyBGPPeers")

        assert result.exists()
        assert result.name == "VerifyBGPPeers.yaml"
        assert result.parent == tmp_path

    def test_save_learned_state_with_hostname(self, tmp_path: Path) -> None:
        """save_learned_state includes hostname in filename for D2D tests."""
        data: dict[str, Any] = {"state": "captured"}
        result = save_learned_state(
            data, tmp_path, "VerifyBGPPeers", hostname="router-01"
        )

        assert result.name == "VerifyBGPPeers_router-01.yaml"

    def test_save_learned_state_creates_directory(self, tmp_path: Path) -> None:
        """save_learned_state creates output directory if it doesn't exist."""
        nested_dir = tmp_path / "deep" / "nested" / "dir"
        data: dict[str, Any] = {"test": True}
        result = save_learned_state(data, nested_dir, "TestCapture")

        assert result.exists()
        assert nested_dir.exists()

    def test_save_learned_state_sanitizes_hostname(self, tmp_path: Path) -> None:
        """save_learned_state handles special characters in hostname."""
        data: dict[str, Any] = {"test": True}
        result = save_learned_state(
            data, tmp_path, "Test", hostname="router/with/slashes"
        )

        assert "/" not in result.name
        assert result.name == "Test_router_with_slashes.yaml"

    def test_load_learned_state_returns_empty_for_missing_file(self) -> None:
        """load_learned_state returns empty dict for non-existent file."""
        result = load_learned_state(Path("/nonexistent/path.yaml"))
        assert result == {}

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Data survives a save → load roundtrip."""
        data: dict[str, Any] = {
            "sdwan": {
                "sites": [
                    {
                        "id": 100,
                        "routers": [
                            {
                                "device_variables": {
                                    "system_ip": "10.0.0.1",
                                    "learned_state": {
                                        "bgp_neighbors": [
                                            {
                                                "peer_addr": "10.1.1.1",
                                                "state": "established",
                                            }
                                        ]
                                    },
                                }
                            }
                        ],
                    }
                ]
            }
        }
        output_path = save_learned_state(data, tmp_path, "TestRoundtrip")
        loaded = load_learned_state(output_path)

        assert loaded["sdwan"]["sites"][0]["id"] == 100
        neighbors = loaded["sdwan"]["sites"][0]["routers"][0]["device_variables"][
            "learned_state"
        ]["bgp_neighbors"]
        assert neighbors[0]["peer_addr"] == "10.1.1.1"
        assert neighbors[0]["state"] == "established"


class TestCLILearnFlag:
    """Tests for the --learn CLI flag integration."""

    def test_learn_flag_accepted(self) -> None:
        """CLI accepts --learn flag without error."""
        from typer.testing import CliRunner

        from nac_test.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--learn" in result.output
