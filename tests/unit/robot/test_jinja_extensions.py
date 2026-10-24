# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Daniel Schmidt

"""Unit tests for nac_test.robot.jinja_extensions module.

Tests verify that Jinja filters and Jinja tests are identified by the name they
declare (not their file name), that higher priority directories replace lower
ones, and that a name defined twice in one directory is an error.
"""

import logging
import sys
from pathlib import Path

import pytest
from nac_artifacts.testing import write_files

from nac_test.exceptions import TemplateError
from nac_test.robot.jinja_extensions import (
    DirectorySpec,
    LoadedExtension,
    as_directories,
    as_tiers,
    load_jinja_extensions,
)

FILTER_SOURCE = """
class Filter:
    name = "{name}"

    @classmethod
    def filter(cls, value):
        return "{marker}"
"""


def filter_file(name: str, marker: str = "x") -> str:
    return FILTER_SOURCE.format(name=name, marker=marker)


def load(directories: DirectorySpec) -> dict[str, LoadedExtension]:
    return load_jinja_extensions(
        directories,
        class_name="Filter",
        module_name="nac_test.filters",
    )


class TestAsDirectories:
    """Tests for normalizing the filters and tests arguments."""

    def test_none_gives_no_directories(self) -> None:
        """Should return an empty list for None."""
        assert as_directories(None) == []

    def test_single_path(self, tmp_path: Path) -> None:
        """Should wrap a single path in a list."""
        assert as_directories(tmp_path) == [tmp_path]

    def test_string_is_one_path_not_characters(self) -> None:
        """Should treat a string as one path instead of iterating its characters."""
        assert as_directories("filters") == [Path("filters")]

    def test_empty_string_is_no_directory(self) -> None:
        """Should treat an empty string like None."""
        assert as_directories("") == []

    def test_sequence_keeps_order(self) -> None:
        """Should keep the priority order of several paths."""
        assert as_directories([Path("a"), Path("b")]) == [Path("a"), Path("b")]


class TestLoading:
    """Tests for loading extensions from directories."""

    def test_name_comes_from_the_class_not_the_file(self, tmp_path: Path) -> None:
        """Should key extensions by their declared name."""
        directory = write_files(tmp_path / "f", {"whatever.py": filter_file("shout")})

        loaded = load([directory])

        assert list(loaded) == ["shout"]
        assert loaded["shout"].origin == directory
        assert loaded["shout"].cls.filter(None) == "x"

    def test_non_python_files_are_ignored(self, tmp_path: Path) -> None:
        """Should only load .py files."""
        directory = write_files(
            tmp_path / "f",
            {"a.py": filter_file("a"), "README.md": "notes", "b.txt": ""},
        )

        assert list(load([directory])) == ["a"]

    def test_no_directories(self) -> None:
        """Should load nothing without directories."""
        assert load([]) == {}

    def test_higher_priority_directory_replaces_lower(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Should let the first directory (highest priority) win on a name clash."""
        caplog.set_level(logging.INFO, logger="nac_test.robot.jinja_extensions")
        high = write_files(tmp_path / "high", {"x.py": filter_file("f", "high")})
        low = write_files(
            tmp_path / "low",
            {"y.py": filter_file("f", "low"), "z.py": filter_file("g")},
        )

        loaded = load([high, low])

        assert loaded["f"].cls.filter(None) == "high"
        assert loaded["f"].origin == high
        assert loaded["g"].origin == low
        assert "replaces the one from" in caplog.text

    def test_file_name_is_irrelevant_for_replacement(self, tmp_path: Path) -> None:
        """Should replace by name even if the files are named differently."""
        high = write_files(tmp_path / "high", {"new_name.py": filter_file("f", "high")})
        low = write_files(tmp_path / "low", {"old_name.py": filter_file("f", "low")})

        assert load([high, low])["f"].cls.filter(None) == "high"

    def test_duplicate_name_in_one_directory_raises(self, tmp_path: Path) -> None:
        """Should not silently pick one of two files declaring the same name."""
        directory = write_files(
            tmp_path / "f",
            {"a.py": filter_file("dup"), "b.py": filter_file("dup")},
        )

        with pytest.raises(
            TemplateError, match=r"Duplicate filter name 'dup'.*a\.py.*b\.py"
        ):
            load([directory])

    def test_same_name_in_different_directories_is_not_a_duplicate(
        self, tmp_path: Path
    ) -> None:
        """Should only treat clashes inside one directory as an error."""
        one = write_files(tmp_path / "one", {"a.py": filter_file("f")})
        two = write_files(tmp_path / "two", {"a.py": filter_file("f")})

        assert list(load([one, two])) == ["f"]

    def test_file_without_the_class_raises(self, tmp_path: Path) -> None:
        """Should fail loudly when a file does not define Filter."""
        directory = write_files(tmp_path / "f", {"a.py": "x = 1\n"})

        with pytest.raises(AttributeError):
            load([directory])

    def test_jinja_tests_use_their_own_class(self, tmp_path: Path) -> None:
        """Should load Test classes and reject duplicate names the same way."""
        source = 'class Test:\n    name = "t"\n    @classmethod\n    def test(cls, v):\n        return True\n'
        directory = write_files(tmp_path / "t", {"a.py": source, "b.py": source})

        with pytest.raises(TemplateError, match="Duplicate test name 't'"):
            load_jinja_extensions(
                [directory],
                class_name="Test",
                module_name="nac_test.tests",
            )

    def test_loading_is_deterministic(self, tmp_path: Path) -> None:
        """Should load files in sorted order regardless of directory listing order."""
        directory = write_files(
            tmp_path / "f",
            {
                "c.py": filter_file("c"),
                "a.py": filter_file("a"),
                "b.py": filter_file("b"),
            },
        )

        assert list(load([directory])) == ["a", "b", "c"]


class TestModuleLoading:
    """Tests for how extension files are imported."""

    def test_no_bytecode_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should not create __pycache__ in extension directories."""
        monkeypatch.setattr(sys, "dont_write_bytecode", False)
        directory = write_files(tmp_path / "f", {"a.py": filter_file("a")})

        load([directory])

        assert not list(tmp_path.rglob("__pycache__"))
        assert sys.dont_write_bytecode is False

    def test_each_file_gets_its_own_module(self, tmp_path: Path) -> None:
        """Should register same-named files of different directories separately."""
        one = write_files(tmp_path / "one", {"a.py": filter_file("f1")})
        two = write_files(tmp_path / "two", {"a.py": filter_file("f2")})

        loaded = load([[one, two]])

        modules = {n: e.cls.__module__ for n, e in loaded.items()}
        assert modules["f1"] != modules["f2"]
        assert all(m.startswith("nac_test.filters.a_") for m in modules.values())
        for name, extension in loaded.items():
            assert sys.modules[modules[name]].Filter is extension.cls

    def test_file_names_that_are_not_identifiers(self, tmp_path: Path) -> None:
        """Should load files whose names contain characters like dashes."""
        directory = write_files(tmp_path / "f", {"my-filter.py": filter_file("m")})

        loaded = load([directory])

        assert loaded["m"].cls.__module__.startswith("nac_test.filters.my_filter_")


class TestTiers:
    """Tests for peer directories (several bundles) in one priority tier."""

    def test_as_tiers_of_plain_paths(self) -> None:
        """Should give one tier per path."""
        assert as_tiers([Path("a"), Path("b")]) == [[Path("a")], [Path("b")]]

    def test_as_tiers_with_peers(self) -> None:
        """Should keep a nested sequence together as one tier of peers."""
        value: DirectorySpec = [Path("local"), [Path("a"), Path("b")], Path("module")]

        assert as_tiers(value) == [
            [Path("local")],
            [Path("a"), Path("b")],
            [Path("module")],
        ]

    def test_as_tiers_single_values(self) -> None:
        """Should accept None, a string and a single path."""
        assert as_tiers(None) == []
        assert as_tiers("") == []
        assert as_tiers("f") == [[Path("f")]]
        assert as_tiers(Path("f")) == [[Path("f")]]

    def test_as_tiers_drops_empty_tiers(self) -> None:
        """Should ignore an empty group of peers."""
        assert as_tiers([Path("a"), []]) == [[Path("a")]]

    def test_as_directories_flattens_tiers(self) -> None:
        """Should list every directory, e.g. to exclude them from discovery."""
        value: DirectorySpec = [Path("local"), [Path("a"), Path("b")]]

        assert as_directories(value) == [Path("local"), Path("a"), Path("b")]

    def test_peers_with_different_names_are_combined(self, tmp_path: Path) -> None:
        """Should load the filters of every peer directory."""
        a = write_files(tmp_path / "a", {"x.py": filter_file("fa")})
        b = write_files(tmp_path / "b", {"y.py": filter_file("fb")})

        loaded = load([[a, b]])

        assert {name: ext.origin for name, ext in loaded.items()} == {"fa": a, "fb": b}

    def test_same_name_in_two_peers_raises_naming_both(self, tmp_path: Path) -> None:
        """Should refuse a filter two peer directories both provide."""
        a = write_files(tmp_path / "a", {"x.py": filter_file("dup")})
        b = write_files(tmp_path / "b", {"y.py": filter_file("dup")})

        with pytest.raises(
            TemplateError, match=r"Filter 'dup' is provided by both .*a and .*b"
        ):
            load([[a, b]])

    def test_a_peer_replaces_a_lower_tier(self, tmp_path: Path) -> None:
        """Should let a peer directory replace the module's filter of the same name."""
        a = write_files(tmp_path / "a", {"x.py": filter_file("f", "a")})
        b = write_files(tmp_path / "b", {"y.py": filter_file("g", "b")})
        module = write_files(tmp_path / "m", {"z.py": filter_file("f", "module")})

        loaded = load([[a, b], module])

        assert loaded["f"].cls.filter(None) == "a"
        assert loaded["g"].origin == b

    def test_same_name_in_different_tiers_is_not_a_conflict(
        self, tmp_path: Path
    ) -> None:
        """Should only treat clashes inside one tier as an error."""
        high = write_files(tmp_path / "h", {"x.py": filter_file("f", "high")})
        low = write_files(tmp_path / "l", {"x.py": filter_file("f", "low")})

        assert load([high, low])["f"].cls.filter(None) == "high"
