# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Integration tests replicating downstream CI pipeline usage of compatibility shims.

These tests exercise the full backward-compatibility shim layer end-to-end,
using the exact API patterns found in downstream repos (nac-aci, nac-catalystcenter,
nac-iosxe, nac-iosxr, nac-meraki, nac-sdwan). All paths are passed as str
(not Path) to verify that the shim's str→Path coercion works correctly in
a realistic pipeline scenario.
"""

import json
import warnings
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]


def test_deploy_template_rendering_via_shim(tmp_path: Path) -> None:
    """Verify shim RobotWriter renders deploy templates that produce valid JSON.

    Replicates the downstream CI pattern: full_apic_test() → render_templates()
    → validate_json(). All paths are passed as str to exercise the shim's
    str→Path coercion.
    """
    fixtures = "tests/integration/fixtures/compat"
    data_dir = f"{fixtures}/data"
    deploy_dir = f"{fixtures}/deploy"
    output_dir = f"{tmp_path}/rendered"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from nac_test.robot_writer import RobotWriter

        writer = RobotWriter([data_dir], "", "")
        # Intentionally passing str (not Path) — downstream repos do this
        writer.write(deploy_dir, output_dir)  # type: ignore[arg-type]

    # Verify the single expected rendered file is valid JSON
    rendered_dir = Path(output_dir)
    rendered_files = [f for f in rendered_dir.iterdir() if f.is_file()]
    assert rendered_files == [rendered_dir / "config.j2"]
    data = json.loads((rendered_dir / "config.j2").read_text())
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "ABC"
    assert data[1]["name"] == "DEF"


def test_robot_render_and_run_via_shim(tmp_path: Path) -> None:
    """Verify shim RobotWriter + run_pabot executes rendered robot tests.

    Replicates the downstream CI pattern: apic_render_run_tests() renders
    robot templates then runs them via pabot. All paths are str to exercise
    the shim layer's str→Path coercion end-to-end.
    """
    fixtures = "tests/integration/fixtures/compat"
    data_dir = f"{fixtures}/data"
    tests_dir = f"{fixtures}/tests"
    output_dir = f"{tmp_path}/robot_output"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import nac_test.pabot
        from nac_test.robot_writer import RobotWriter

        writer = RobotWriter([data_dir], "", "")
        # Intentionally passing str (not Path) — downstream repos do this
        writer.write(tests_dir, output_dir)  # type: ignore[arg-type]
        exit_code = nac_test.pabot.run_pabot(output_dir)

    assert exit_code == 0, f"pabot returned exit code {exit_code}, expected 0"
