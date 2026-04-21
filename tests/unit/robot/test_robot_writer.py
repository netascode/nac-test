# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# mypy: disable-error-code="no-untyped-def"

"""Unit tests for RobotWriter.

Covers:
- render_template: uses self.data as template context by default
- render_template: custom_data overrides self.data when provided
- render_template: output file and parent directories are created
"""

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from nac_test.robot.robot_writer import KeyFirstEnvironment, RobotWriter

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


class _MappingWithTagAttr(dict[str, object]):
    @property
    def tag(self) -> None:
        return None


class TestKeyFirstEnvironment:
    def test_missing_key_returns_undefined_instead_of_attribute(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "t.robot").write_text(
            "{{ child.tag | default(defaults.tag) }}\n{{ child.tag is defined }}\n"
        )

        env = KeyFirstEnvironment(loader=FileSystemLoader(str(tmp_path)))  # nosec B701
        template = env.get_template("t.robot")

        rendered = template.render(
            child=_MappingWithTagAttr({}),
            defaults={"tag": "fallback"},
        )
        lines = rendered.splitlines()
        assert lines[0] == "fallback"
        assert lines[1] == "False"

    def test_existing_key_wins_over_attribute(self, tmp_path: Path) -> None:
        (tmp_path / "t.robot").write_text("{{ child.tag }}\n")

        env = KeyFirstEnvironment(loader=FileSystemLoader(str(tmp_path)))  # nosec B701
        template = env.get_template("t.robot")

        rendered = template.render(child=_MappingWithTagAttr({"tag": 100}))
        assert rendered.strip() == "100"
