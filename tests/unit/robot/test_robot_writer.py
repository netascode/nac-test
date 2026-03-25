# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# mypy: disable-error-code="no-untyped-def"

"""Unit tests for RobotWriter.

Covers:
- Constructor: merged_data dict is stored directly (no file I/O, no conversion)
- render_template: uses self.data as template context by default
- render_template: custom_data overrides self.data when provided
- render_template: output file and parent directories are created
"""

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from nac_test.robot.robot_writer import RobotWriter

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def templates_dir(tmp_path: Path) -> Path:
    """Temporary directory with a minimal Jinja2 robot template."""
    (tmp_path / "simple.robot").write_text(
        "*** Test Cases ***\nTest {{ device }}\n    Log    ok\n"
    )
    return tmp_path


@pytest.fixture
def jinja_env(templates_dir: Path) -> Environment:
    """Jinja2 environment rooted at templates_dir."""
    return Environment(loader=FileSystemLoader(str(templates_dir)))  # nosec B701


@pytest.fixture
def writer() -> RobotWriter:
    """RobotWriter with a simple data dict matching the simple.robot template."""
    return RobotWriter(
        merged_data={"device": "Router1", "vlan": 100},
        filters_path=None,
        tests_path=None,
    )


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


class TestRobotWriterInit:
    """Tests for RobotWriter.__init__()."""

    def test_stores_merged_data_directly(self) -> None:
        """Constructor stores the dict by reference — no copy or type conversion."""
        data = {"host": "sw1", "count": 5}
        w = RobotWriter(merged_data=data, filters_path=None, tests_path=None)
        assert w.data is data

    def test_accepts_empty_dict(self) -> None:
        """Constructor accepts an empty dict without raising."""
        w = RobotWriter(merged_data={}, filters_path=None, tests_path=None)
        assert w.data == {}

    def test_tags_default_to_empty_lists(self) -> None:
        """include_tags and exclude_tags default to empty lists when omitted."""
        w = RobotWriter(merged_data={}, filters_path=None, tests_path=None)
        assert w.include_tags == []
        assert w.exclude_tags == []

    @pytest.mark.parametrize(
        ("include_tags", "exclude_tags"),
        [
            (["smoke"], []),
            ([], ["slow"]),
            (["smoke"], ["slow"]),
            (["smoke", "regression"], ["slow", "wip"]),
        ],
        ids=["include_only", "exclude_only", "both", "multiple_each"],
    )
    def test_tags_stored_correctly(self, include_tags, exclude_tags) -> None:
        """Explicit include/exclude tags are stored without modification."""
        w = RobotWriter(
            merged_data={},
            filters_path=None,
            tests_path=None,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )
        assert w.include_tags == include_tags
        assert w.exclude_tags == exclude_tags


# ---------------------------------------------------------------------------
# render_template tests
# ---------------------------------------------------------------------------


class TestRobotWriterRenderTemplate:
    """Tests for RobotWriter.render_template()."""

    def test_renders_using_self_data(
        self, writer: RobotWriter, jinja_env: Environment, tmp_path: Path
    ) -> None:
        """render_template uses self.data as context when no custom_data is given."""
        output = tmp_path / "out.robot"
        writer.render_template(
            template_path=Path("simple.robot"),
            output_path=output,
            env=jinja_env,
        )
        content = output.read_text()
        assert "Router1" in content
        assert "{{" not in content

    def test_custom_data_overrides_self_data(
        self, writer: RobotWriter, jinja_env: Environment, tmp_path: Path
    ) -> None:
        """custom_data replaces self.data entirely as the template context."""
        output = tmp_path / "out.robot"
        writer.render_template(
            template_path=Path("simple.robot"),
            output_path=output,
            env=jinja_env,
            custom_data={"device": "Switch99"},
        )
        content = output.read_text()
        assert "Switch99" in content
        assert "Router1" not in content

    def test_creates_output_file_and_parent_directories(
        self, writer: RobotWriter, jinja_env: Environment, tmp_path: Path
    ) -> None:
        """render_template creates the output file and any missing parent directories."""
        output = tmp_path / "a" / "b" / "out.robot"
        writer.render_template(
            template_path=Path("simple.robot"),
            output_path=output,
            env=jinja_env,
        )
        assert output.exists()
        assert output.parent.is_dir()
