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
from typing import Any

import pytest
from jinja2 import Environment, FileSystemLoader

from nac_test.exceptions import TemplateError
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
        assert output.read_text().strip()  # non-empty content


# ---------------------------------------------------------------------------
# _chunk_nested_objects tests
# ---------------------------------------------------------------------------


class TestChunkNestedObjects:
    """Tests for RobotWriter._chunk_nested_objects()."""

    def test_one_level_object_path_chunks(self, writer: RobotWriter) -> None:
        """A single-level object_path chunks a list that is a direct child."""
        data = {"hosts": [{"name": f"h{i}"} for i in range(3)]}
        chunks = writer._chunk_nested_objects(data, "hosts", 2)
        assert [[h["name"] for h in c["hosts"]] for c in chunks] == [
            ["h0", "h1"],
            ["h2"],
        ]

    def test_nested_object_path_chunks_leaf_under_dict_parent(
        self, writer: RobotWriter
    ) -> None:
        """2-level object_path whose parent is a dict"""
        domain: dict[str, Any] = {
            "name": "Global",
            "objects": {
                "hosts": [{"name": f"h{i}"} for i in range(5)],
                "networks": [{"name": "n1"}],
            },
        }
        chunks = writer._chunk_nested_objects(domain, "objects.hosts", 2)

        # 5 hosts at chunk size 2 -> 3 chunks of 2, 2, 1.
        assert [len(c["objects"]["hosts"]) for c in chunks] == [2, 2, 1]
        # Hosts are partitioned in order with no loss or overlap.
        flat = [h["name"] for c in chunks for h in c["objects"]["hosts"]]
        assert flat == [f"h{i}" for i in range(5)]
        # Sibling object types are preserved untouched in every chunk.
        assert all(c["objects"]["networks"] == [{"name": "n1"}] for c in chunks)
        # The original input is not mutated.
        assert len(domain["objects"]["hosts"]) == 5

    def test_dict_nested_non_list_child_returns_original(
        self, writer: RobotWriter
    ) -> None:
        """A dict parent whose child is not a list yields the item unchanged."""
        data = {"objects": {"hosts": "not-a-list"}}
        assert writer._chunk_nested_objects(data, "objects.hosts", 2) == [data]

    def test_nested_object_path_chunks_leaf_under_list_parent(
        self, writer: RobotWriter
    ) -> None:
        """2-level object_path whose parent is a list"""
        data = {
            "services": [
                {
                    "name": "s1",
                    "endpoints": [{"name": "e1"}, {"name": "e2"}, {"name": "e3"}],
                },
                {"name": "s2", "endpoints": [{"name": "e4"}]},
                {"name": "s3", "endpoints": [{"name": "e5"}]},
            ]
        }
        chunks = writer._chunk_nested_objects(data, "services.endpoints", 2)

        assert len(chunks) == 3
        assert [p["name"] for p in chunks[0]["services"]] == ["s1"]
        assert [e["name"] for e in chunks[0]["services"][0]["endpoints"]] == [
            "e1",
            "e2",
        ]
        assert [p["name"] for p in chunks[1]["services"]] == ["s1", "s2"]
        assert [e["name"] for e in chunks[1]["services"][0]["endpoints"]] == ["e3"]
        assert [e["name"] for e in chunks[1]["services"][1]["endpoints"]] == ["e4"]
        assert [p["name"] for p in chunks[2]["services"]] == ["s3"]
        assert [e["name"] for e in chunks[2]["services"][0]["endpoints"]] == ["e5"]


# ---------------------------------------------------------------------------
# Filter and Jinja test directories (layers)
# ---------------------------------------------------------------------------

FILTER_SOURCE = (
    'class Filter:\n    name = "{name}"\n\n    @classmethod\n'
    '    def filter(cls, value):\n        return "{marker}"\n'
)
TEST_SOURCE = (
    'class Test:\n    name = "{name}"\n\n    @classmethod\n'
    "    def test(cls, value):\n        return {result}\n"
)


def make_filters(directory: Path, **markers: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, marker in markers.items():
        (directory / f"{name}.py").write_text(
            FILTER_SOURCE.format(name=name, marker=marker)
        )
    return directory


class TestExtensionDirectories:
    """RobotWriter loads filters and Jinja tests from one or several directories."""

    def test_single_directory_is_still_accepted(self, tmp_path: Path) -> None:
        """Should keep accepting a plain Path for filters and tests."""
        filters = make_filters(tmp_path / "f", shout="loud")
        tests = tmp_path / "t"
        tests.mkdir()
        (tests / "positive.py").write_text(
            TEST_SOURCE.format(name="positive", result="value > 0")
        )

        writer = RobotWriter({}, filters, tests)

        assert list(writer.filters) == ["shout"]
        assert list(writer.tests) == ["positive"]

    def test_no_directories(self) -> None:
        """Should have no filters or tests without directories."""
        writer = RobotWriter({}, None, None)

        assert writer.filters == {} and writer.tests == {}

    def test_several_directories_merge_with_priority(self, tmp_path: Path) -> None:
        """Should let the first directory win and keep the others' extra names."""
        high = make_filters(tmp_path / "high", shout="high")
        low = make_filters(tmp_path / "low", shout="low", whisper="low")

        writer = RobotWriter({}, [high, low], None)

        assert writer.filters["shout"].filter(None) == "high"
        assert writer.filters["whisper"].filter(None) == "low"
        assert writer.filter_origins == {"shout": high, "whisper": low}

    def test_jinja_test_origins(self, tmp_path: Path) -> None:
        """Should remember which directory each Jinja test came from."""
        tests = tmp_path / "t"
        tests.mkdir()
        (tests / "a.py").write_text(TEST_SOURCE.format(name="a", result="True"))

        writer = RobotWriter({}, None, [tests])

        assert writer.test_origins == {"a": tests}

    def test_duplicate_filter_names_in_one_directory_raise(
        self, tmp_path: Path
    ) -> None:
        """Should refuse two filter files declaring the same name."""
        directory = make_filters(tmp_path / "f", one="x")
        (directory / "two.py").write_text(FILTER_SOURCE.format(name="one", marker="y"))

        with pytest.raises(TemplateError, match="Duplicate filter name 'one'"):
            RobotWriter({}, directory, None)

    def test_filters_are_usable_when_rendering(self, tmp_path: Path) -> None:
        """Should register merged filters in the Jinja environment used for output."""
        filters = make_filters(tmp_path / "f", shout="LOUD")
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "a.robot").write_text("*** Test Cases ***\n{{ 'x' | shout }}\n")
        out = tmp_path / "out"

        RobotWriter({}, [filters], None).write(templates, out)

        assert "LOUD" in (out / "a.robot").read_text()
