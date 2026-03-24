# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for nac_test.utils.path_utils."""

import os
from pathlib import Path

from nac_test.utils.path_utils import derive_test_name


class TestDeriveTestName:
    """Tests for derive_test_name()."""

    def test_derives_name_from_testscript_path(self) -> None:
        """Simple one-level subdirectory produces dot-notation name."""
        result = derive_test_name(
            Path("/path/to/templates/nrfu/verify_device_status.py"),
            Path("/path/to/templates"),
            fallback="fallback",
        )
        assert result == "nrfu.verify_device_status"

    def test_handles_nested_test_directories(self) -> None:
        """Deeply nested path produces multi-part dot-notation name."""
        result = derive_test_name(
            Path("/path/to/templates/api/tenants/verify_tenant.py"),
            Path("/path/to/templates"),
            fallback="fallback",
        )
        assert result == "api.tenants.verify_tenant"

    def test_handles_d2d_test_paths(self) -> None:
        """D2D-style nested path produces correct dot-notation name."""
        result = derive_test_name(
            Path("/path/to/templates/d2d/operational/verify_bgp.py"),
            Path("/path/to/templates"),
            fallback="fallback",
        )
        assert result == "d2d.operational.verify_bgp"

    def test_root_level_test_returns_stem(self) -> None:
        """Test file directly under test_dir (no subdirectory) returns bare stem."""
        result = derive_test_name(
            Path("/path/to/templates/verify_device.py"),
            Path("/path/to/templates"),
            fallback="fallback",
        )
        assert result == "verify_device"

    def test_falls_back_when_path_not_under_test_dir(self) -> None:
        """Path outside test_dir returns the provided fallback."""
        result = derive_test_name(
            Path("/completely/different/path/verify.py"),
            Path("/path/to/templates"),
            fallback="my_fallback",
        )
        assert result == "my_fallback"

    def test_handles_real_world_sdwan_path(self) -> None:
        """Real-world SD-WAN path produces correct dot-notation name."""
        result = derive_test_name(
            Path(
                "/Users/username/Desktop/Automation/testing-for-nac/"
                "nac-sdwan-terraform/pyats/nrfu/verify_sdwanmanager_device_status.py"
            ),
            Path(
                "/Users/username/Desktop/Automation/testing-for-nac/"
                "nac-sdwan-terraform/pyats"
            ),
            fallback="fallback",
        )
        assert result == "nrfu.verify_sdwanmanager_device_status"


class TestDeriveTestNameSymlinks:
    """Tests for derive_test_name() with a symlinked test_dir.

    derive_test_name uses absolute() rather than resolve(). When test_dir is a
    symlink, resolve() would follow it (potentially breaking the relative_to
    comparison), while absolute() preserves the symlink and keeps both sides
    comparable. These tests verify that behaviour.
    """

    def test_symlinked_test_dir_still_derives_correct_name(
        self, tmp_path: Path
    ) -> None:
        """When test_dir itself is a symlink, paths under it still derive correctly.

        absolute() on both testscript_path and test_dir keeps them comparable,
        whereas resolve() would follow the symlink and could break relative_to.
        """
        real_dir = tmp_path / "real_tests"
        real_dir.mkdir()
        (real_dir / "nrfu").mkdir()
        script = real_dir / "nrfu" / "verify_bgp.py"
        script.touch()

        linked_dir = tmp_path / "tests"
        os.symlink(real_dir, linked_dir)

        result = derive_test_name(
            linked_dir / "nrfu" / "verify_bgp.py", linked_dir, fallback="fallback"
        )
        assert result == "nrfu.verify_bgp"
