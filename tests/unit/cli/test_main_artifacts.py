# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Daniel Schmidt

"""Tests for how main.py resolves templates, filters and tests from layers.

The orchestrator is mocked: these tests check what the CLI hands to it and how
it reports problems, for local options as well as bundles and modules.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from nac_artifacts.testing import (
    bundle_files,
    install_module,
    make_zip,
    module_entry,
    overrides_yaml,
    write_files,
    write_modules_json,
)
from typer.testing import CliRunner, Result

from nac_test.cli.main import app
from nac_test.core.constants import EXIT_INVALID_ARGS, MERGED_TEMPLATES_DIRNAME
from nac_test.core.types import CombinedResults, TestResults
from nac_test.utils.terminal import TerminalColors

runner = CliRunner()


def _plain(result: Result) -> str:
    """CLI output without ANSI styling (kept by nac-test unless NO_COLOR is set)."""
    return TerminalColors.strip_ansi(result.output)


ROBOT = "*** Test Cases ***\nCase\n    Log    {text}\n"
FILTER = 'class Filter:\n    name = "{name}"\n\n    @classmethod\n    def filter(cls, v):\n        return v\n'


@pytest.fixture
def orchestrator_cls() -> Iterator[Mock]:
    """Mocked CombinedOrchestrator class that reports one passing test."""
    with patch("nac_test.cli.main.CombinedOrchestrator") as cls:
        cls.return_value.run_tests.return_value = CombinedResults(
            robot=TestResults(passed=1, failed=0, skipped=0)
        )
        yield cls


@pytest.fixture
def dirs(project: Path) -> dict[str, Path]:
    """Data and output directories inside the project."""
    data = project / "data"
    data.mkdir()
    return {"data": data, "output": project / "output"}


def invoke(dirs: dict[str, Path], *args: str, with_dirs: bool = True) -> Result:
    base = ["-d", str(dirs["data"]), "-o", str(dirs["output"])] if with_dirs else []
    return runner.invoke(app, [*base, *args])


def kwargs_of(orchestrator_cls: Mock) -> dict[str, Any]:
    kwargs: dict[str, Any] = dict(orchestrator_cls.call_args.kwargs)
    return kwargs


def module_files(**extra: str) -> dict[str, str]:
    return {"tests/templates/module.robot": ROBOT.format(text="module"), **extra}


class TestRequiredOptions:
    """-d and -o stay required (they are optional only for --list-artifacts)."""

    def test_missing_data_option(self, dirs: dict[str, Path]) -> None:
        """Should fail with exit code 2 and name the option."""
        result = runner.invoke(app, ["-o", str(dirs["output"])])

        assert result.exit_code == EXIT_INVALID_ARGS
        assert "Missing option '--data' / '-d'" in _plain(result)

    def test_missing_output_option(self, dirs: dict[str, Path]) -> None:
        """Should fail with exit code 2 and name the option."""
        result = runner.invoke(app, ["-d", str(dirs["data"])])

        assert result.exit_code == EXIT_INVALID_ARGS
        assert "Missing option '--output' / '-o'" in _plain(result)


class TestLocalTemplatesOnly:
    """Behaviour without any module or bundle must not change."""

    def test_single_directory_is_passed_through_unchanged(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should hand the -t directory to the orchestrator as is, without a copy."""
        templates = write_files(project / "templates", {"a.robot": "x"})

        result = invoke(dirs, "-t", str(templates))

        assert result.exit_code == 0
        assert kwargs_of(orchestrator_cls)["templates_dir"] == templates
        assert kwargs_of(orchestrator_cls)["filters_path"] is None
        assert kwargs_of(orchestrator_cls)["tests_path"] is None
        assert not (dirs["output"] / MERGED_TEMPLATES_DIRNAME).exists()

    def test_single_filter_and_test_directories_stay_paths(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should pass -f and --tests as plain paths, not lists."""
        templates = write_files(project / "templates", {"a.robot": "x"})
        filters = write_files(project / "filters", {})
        jinja_tests = write_files(project / "jinja_tests", {})

        invoke(
            dirs, "-t", str(templates), "-f", str(filters), "--tests", str(jinja_tests)
        )

        assert kwargs_of(orchestrator_cls)["filters_path"] == filters
        assert kwargs_of(orchestrator_cls)["tests_path"] == jinja_tests

    def test_no_templates_anywhere_is_an_error(
        self, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should fail with exit code 2 instead of silently running nothing."""
        result = invoke(dirs)

        assert result.exit_code == EXIT_INVALID_ARGS
        assert "No test templates found" in _plain(result)
        orchestrator_cls.assert_not_called()


class TestPackagedTemplates:
    """Templates, filters and Jinja tests from modules and bundles."""

    def test_module_templates_without_the_templates_option(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should run with a module's templates and filters when -t is absent."""
        module_dir = install_module(
            project,
            module_files(**{"tests/jinja_filters/f.py": FILTER.format(name="f")}),
        )

        result = invoke(dirs)

        nac_dir = module_dir.resolve() / "nac"
        assert result.exit_code == 0
        assert (
            kwargs_of(orchestrator_cls)["templates_dir"] == nac_dir / "tests/templates"
        )
        assert (
            kwargs_of(orchestrator_cls)["filters_path"]
            == nac_dir / "tests/jinja_filters"
        )

    def test_local_and_module_templates_are_merged(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should merge both, with the local template replacing the module's."""
        install_module(
            project,
            {
                "tests/templates/shared.robot": ROBOT.format(text="module"),
                "tests/templates/module_only.robot": ROBOT.format(text="module only"),
            },
        )
        local = write_files(
            project / "templates", {"shared.robot": ROBOT.format(text="local")}
        )

        result = invoke(dirs, "-t", str(local))

        merged = kwargs_of(orchestrator_cls)["templates_dir"]
        assert result.exit_code == 0
        assert merged == (dirs["output"] / MERGED_TEMPLATES_DIRNAME).absolute()
        assert "local" in (merged / "shared.robot").read_text()
        assert (merged / "module_only.robot").exists()

    def test_bundle_replaces_module_templates(
        self,
        project: Path,
        dirs: dict[str, Path],
        tmp_path: Path,
        orchestrator_cls: Mock,
    ) -> None:
        """Should rank a bundle above the module for the same relative path."""
        install_module(
            project, {"tests/templates/a.robot": ROBOT.format(text="module")}
        )
        archive = make_zip(
            tmp_path / "acme-nxos-1.0.0.zip",
            bundle_files({"tests/templates/a.robot": ROBOT.format(text="bundle")}),
        )

        result = invoke(dirs, "--bundle", str(archive))

        merged = kwargs_of(orchestrator_cls)["templates_dir"]
        assert result.exit_code == 0
        assert "bundle" in (merged / "a.robot").read_text()

    def test_filter_directories_are_passed_in_priority_order(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should give the orchestrator local first, then module, filter directories."""
        module_dir = install_module(
            project,
            module_files(**{"tests/jinja_filters/f.py": FILTER.format(name="f")}),
        )
        local_filters = write_files(project / "filters", {})
        local_templates = write_files(project / "templates", {"a.robot": "x"})

        invoke(dirs, "-t", str(local_templates), "-f", str(local_filters))

        assert kwargs_of(orchestrator_cls)["filters_path"] == [
            local_filters,
            module_dir.resolve() / "nac/tests/jinja_filters",
        ]

    def test_filters_inside_the_templates_directory_are_not_merged(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should keep filter files out of the merged tree (PyATS must not see them)."""
        install_module(project, module_files())
        local = write_files(
            project / "tests",
            {"a.robot": "x", "filters/f.py": FILTER.format(name="f")},
        )

        invoke(dirs, "-t", str(local), "-f", str(local / "filters"))

        merged = kwargs_of(orchestrator_cls)["templates_dir"]
        assert (merged / "a.robot").exists()
        assert not (merged / "filters").exists()

    def test_bundle_environment_variable(
        self,
        project: Path,
        dirs: dict[str, Path],
        tmp_path: Path,
        orchestrator_cls: Mock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should read the bundle location from NAC_TEST_BUNDLE."""
        archive = make_zip(
            tmp_path / "b.zip", bundle_files({"tests/templates/a.robot": "x"})
        )
        monkeypatch.setenv("NAC_TEST_BUNDLE", str(archive))

        result = invoke(dirs)

        assert result.exit_code == 0
        assert kwargs_of(orchestrator_cls)["templates_dir"].name == "templates"

    def test_module_dir_environment_variable(
        self,
        project: Path,
        dirs: dict[str, Path],
        orchestrator_cls: Mock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should read the module directory from NAC_TEST_MODULE_DIR."""
        write_files(project / "mod/nac", {"tests/templates/a.robot": "x"})
        monkeypatch.setenv("NAC_TEST_MODULE_DIR", "mod")

        result = invoke(dirs)

        assert result.exit_code == 0


class TestPackagedErrors:
    """Problems with bundles and modules are reported as invalid arguments."""

    def test_missing_bundle(
        self, dirs: dict[str, Path], orchestrator_cls: Mock, tmp_path: Path
    ) -> None:
        """Should fail with exit code 2 before running anything."""
        result = invoke(dirs, "--bundle", str(tmp_path / "missing.zip"))

        assert result.exit_code == EXIT_INVALID_ARGS
        assert "Bundle not found" in _plain(result)
        orchestrator_cls.assert_not_called()

    def test_ambiguous_modules_name_the_cli_option(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should tell the user to pick a module with --module-dir."""
        for key in ("a", "b"):
            write_files(project / f".terraform/modules/{key}/nac", module_files())
        write_modules_json(
            project, [module_entry(k, f".terraform/modules/{k}") for k in ("a", "b")]
        )

        result = invoke(dirs)

        assert result.exit_code == EXIT_INVALID_ARGS
        assert "--module-dir" in _plain(result)


class TestListArtifacts:
    """--list-artifacts shows what would be used and exits."""

    def test_works_without_data_and_output(
        self, project: Path, orchestrator_cls: Mock
    ) -> None:
        """Should not require -d and -o, and never run the orchestrator."""
        local = write_files(project / "templates", {"a.robot": "x"})

        result = runner.invoke(app, ["--list-artifacts", "-t", str(local)])

        assert result.exit_code == 0
        assert f"templates {local} [local]" in _plain(result)
        orchestrator_cls.assert_not_called()

    def test_shows_layers_replaced_templates_and_extensions(
        self, project: Path, orchestrator_cls: Mock
    ) -> None:
        """Should list layers, shadowed templates, filters and their origins."""
        install_module(
            project,
            {
                "tests/templates/shared.robot": "module",
                "tests/jinja_filters/mod.py": FILTER.format(name="mod_filter"),
            },
            version="0.3.0",
        )
        local = write_files(project / "templates", {"shared.robot": "local"})
        local_filters = write_files(
            project / "filters", {"loc.py": FILTER.format(name="loc_filter")}
        )

        result = runner.invoke(
            app, ["--list-artifacts", "-t", str(local), "-f", str(local_filters)]
        )

        assert result.exit_code == 0
        assert "module 'm' 0.3.0 at" in _plain(result)
        assert "shared.robot [local] shadows [module]" in _plain(result)
        assert "loc_filter [local]" in _plain(result)
        assert "mod_filter [module]" in _plain(result)

    def test_does_not_write_into_the_output_directory(
        self, project: Path, dirs: dict[str, Path]
    ) -> None:
        """Should only read: no merged tree is created while listing."""
        install_module(project, module_files())
        local = write_files(project / "templates", {"a.robot": "x"})

        invoke(dirs, "--list-artifacts", "-t", str(local))

        assert not dirs["output"].exists()

    def test_reports_duplicate_filter_names(self, project: Path) -> None:
        """Should fail with exit code 2 and explain the duplicate."""
        filters = write_files(
            project / "filters",
            {"a.py": FILTER.format(name="dup"), "b.py": FILTER.format(name="dup")},
        )

        result = runner.invoke(app, ["--list-artifacts", "-f", str(filters)])

        assert result.exit_code == EXIT_INVALID_ARGS
        assert "Duplicate filter name 'dup'" in _plain(result)

    def test_with_nothing_to_show(self, project: Path) -> None:
        """Should still succeed and say there are no templates."""
        result = runner.invoke(app, ["--list-artifacts"])

        assert result.exit_code == 0
        assert "Templates:\n  none" in _plain(result)


class TestDisabledTemplates:
    """overrides.yaml removes templates of lower layers."""

    @staticmethod
    def project_overrides(project: Path, **kwargs: list[str]) -> None:
        write_files(project / ".nac", {"overrides.yaml": overrides_yaml(**kwargs)})

    def test_module_template_is_disabled_from_the_project(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should hand over a tree without the disabled module template."""
        install_module(
            project,
            {
                "tests/templates/keep.robot": ROBOT.format(text="keep"),
                "tests/templates/drop.robot": ROBOT.format(text="drop"),
            },
        )
        self.project_overrides(project, templates=["drop.robot"])

        result = invoke(dirs)

        used = kwargs_of(orchestrator_cls)["templates_dir"]
        assert result.exit_code == 0
        assert used == (dirs["output"] / MERGED_TEMPLATES_DIRNAME).absolute()
        assert (used / "keep.robot").exists()
        assert not (used / "drop.robot").exists()

    def test_local_templates_are_never_disabled(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should keep a local template even if an entry matches its path."""
        install_module(project, {"tests/templates/drop.robot": "module"})
        local = write_files(project / "templates", {"drop.robot": "local"})
        self.project_overrides(project, templates=["drop.robot"])

        invoke(dirs, "-t", str(local))

        used = kwargs_of(orchestrator_cls)["templates_dir"]
        assert (used / "drop.robot").read_text() == "local"

    def test_bundle_disables_module_template(
        self,
        project: Path,
        dirs: dict[str, Path],
        tmp_path: Path,
        orchestrator_cls: Mock,
    ) -> None:
        """Should let a bundle's overrides.yaml remove a module template."""
        install_module(
            project,
            {
                "tests/templates/keep.robot": "keep",
                "tests/templates/lib/Utils.py": "# lib",
            },
        )
        archive = make_zip(
            tmp_path / "b.zip",
            bundle_files(
                {"tests/templates/bundle.robot": "bundle"},
                extra={"overrides.yaml": overrides_yaml(templates=["lib/*"])},
            ),
        )

        invoke(dirs, "--bundle", str(archive))

        used = kwargs_of(orchestrator_cls)["templates_dir"]
        assert (used / "keep.robot").exists()
        assert (used / "bundle.robot").exists()
        assert not (used / "lib").exists()

    def test_single_module_source_is_not_copied_without_a_match(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should keep using the module directory in place if no entry matches."""
        module_dir = install_module(project, {"tests/templates/a.robot": "x"})
        self.project_overrides(project, templates=["nothing/here"])

        invoke(dirs)

        used = kwargs_of(orchestrator_cls)["templates_dir"]
        assert used == module_dir.resolve() / "nac/tests/templates"

    def test_malformed_overrides_are_an_invalid_argument_error(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should exit with code 2 and say what is wrong with the file."""
        install_module(project, {"tests/templates/a.robot": "x"})
        write_files(
            project / ".nac", {"overrides.yaml": "disabel:\n  templates: [a]\n"}
        )

        result = invoke(dirs)

        assert result.exit_code == EXIT_INVALID_ARGS
        assert "Unknown key(s) disabel" in _plain(result)
        orchestrator_cls.assert_not_called()

    def test_list_artifacts_shows_disabled_and_unmatched(self, project: Path) -> None:
        """Should show disabled templates and entries that matched nothing."""
        install_module(
            project,
            {
                "tests/templates/keep.robot": "keep",
                "tests/templates/drop.robot": "drop",
            },
        )
        self.project_overrides(project, templates=["drop.robot", "typo/*"])

        result = runner.invoke(app, ["--list-artifacts"])

        assert result.exit_code == 0
        assert "drop.robot [module] disabled by project overrides" in _plain(result)
        assert "typo/* (project overrides)" in _plain(result)
        assert "keep.robot [module]" in _plain(result)

    def test_list_artifacts_without_overrides_is_unchanged(self, project: Path) -> None:
        """Should not print the disable sections when nothing is disabled."""
        install_module(project, {"tests/templates/a.robot": "x"})

        result = runner.invoke(app, ["--list-artifacts"])

        assert "Disabled Templates" not in _plain(result)
        assert "Matching No Template" not in _plain(result)


class TestMultipleBundles:
    """Several bundles are peers: they may split templates, filters and tests."""

    @staticmethod
    def bundle(tmp_path: Path, name: str, files: dict[str, str]) -> Path:
        return make_zip(tmp_path / f"{name}.zip", bundle_files(files, name=name))

    def test_templates_split_across_bundles_are_merged(
        self,
        project: Path,
        dirs: dict[str, Path],
        tmp_path: Path,
        orchestrator_cls: Mock,
    ) -> None:
        """Should run with the templates of every bundle."""
        a = self.bundle(tmp_path, "alpha", {"tests/templates/a.robot": "a"})
        b = self.bundle(tmp_path, "beta", {"tests/templates/b.robot": "b"})

        result = invoke(dirs, "--bundle", str(a), "--bundle", str(b))

        used = kwargs_of(orchestrator_cls)["templates_dir"]
        assert result.exit_code == 0
        assert (used / "a.robot").exists() and (used / "b.robot").exists()

    def test_bundles_in_nac_are_all_used(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should use every archive dropped into .nac/."""
        (project / ".nac").mkdir()
        for name in ("one", "two"):
            make_zip(
                project / ".nac" / f"{name}.zip",
                bundle_files({f"tests/templates/{name}.robot": name}, name=name),
            )

        result = invoke(dirs)

        used = kwargs_of(orchestrator_cls)["templates_dir"]
        assert result.exit_code == 0
        assert (used / "one.robot").exists() and (used / "two.robot").exists()

    def test_overlapping_templates_are_an_invalid_argument_error(
        self,
        project: Path,
        dirs: dict[str, Path],
        tmp_path: Path,
        orchestrator_cls: Mock,
    ) -> None:
        """Should exit with code 2 and name both bundles and the template."""
        a = self.bundle(tmp_path, "alpha", {"tests/templates/x.robot": "a"})
        b = self.bundle(tmp_path, "beta", {"tests/templates/x.robot": "b"})

        result = invoke(dirs, "--bundle", str(a), "--bundle", str(b))

        assert result.exit_code == EXIT_INVALID_ARGS
        assert "'x.robot' is provided by both bundle alpha and bundle beta" in _plain(
            result
        )
        orchestrator_cls.assert_not_called()

    def test_a_bundle_replaces_the_module_template_but_not_a_peer(
        self,
        project: Path,
        dirs: dict[str, Path],
        tmp_path: Path,
        orchestrator_cls: Mock,
    ) -> None:
        """Should let each bundle replace the module's templates at its own paths."""
        install_module(
            project,
            {
                "tests/templates/a.robot": "module a",
                "tests/templates/b.robot": "module b",
            },
        )
        a = self.bundle(tmp_path, "alpha", {"tests/templates/a.robot": "bundle a"})
        b = self.bundle(tmp_path, "beta", {"tests/templates/b.robot": "bundle b"})

        invoke(dirs, "--bundle", str(a), "--bundle", str(b))

        used = kwargs_of(orchestrator_cls)["templates_dir"]
        assert (used / "a.robot").read_text() == "bundle a"
        assert (used / "b.robot").read_text() == "bundle b"

    def test_filter_directories_of_bundles_form_one_tier(
        self,
        project: Path,
        dirs: dict[str, Path],
        tmp_path: Path,
        orchestrator_cls: Mock,
    ) -> None:
        """Should pass the bundles' filter directories as peers, above the module."""
        install_module(
            project,
            module_files(**{"tests/jinja_filters/m.py": FILTER.format(name="m")}),
        )
        a = self.bundle(
            tmp_path,
            "alpha",
            {
                "tests/templates/a.robot": "a",
                "tests/jinja_filters/a.py": FILTER.format(name="fa"),
            },
        )
        b = self.bundle(
            tmp_path, "beta", {"tests/jinja_filters/b.py": FILTER.format(name="fb")}
        )

        invoke(dirs, "--bundle", str(a), "--bundle", str(b))

        tiers = kwargs_of(orchestrator_cls)["filters_path"]
        assert len(tiers) == 2  # the bundles' tier of peers, then the module
        assert len(tiers[0]) == 2 and all(isinstance(p, Path) for p in tiers[0])
        assert all(p.as_posix().endswith("tests/jinja_filters") for p in tiers[0])
        assert isinstance(tiers[1], Path)

    def test_same_bundle_name_twice_is_an_invalid_argument_error(
        self, project: Path, dirs: dict[str, Path], orchestrator_cls: Mock
    ) -> None:
        """Should refuse an old and a new version of one bundle left in .nac/."""
        (project / ".nac").mkdir()
        for version in ("1.0.0", "2.0.0"):
            make_zip(
                project / ".nac" / f"acme-{version}.zip",
                bundle_files(
                    {"tests/templates/a.robot": "x"}, name="acme", version=version
                ),
            )

        result = invoke(dirs)

        assert result.exit_code == EXIT_INVALID_ARGS
        assert "'acme' is present 2 times" in _plain(result)

    def test_bundle_for_another_tool_is_ignored(
        self,
        project: Path,
        dirs: dict[str, Path],
        tmp_path: Path,
        orchestrator_cls: Mock,
    ) -> None:
        """Should skip a detected bundle that only ships a schema and rules."""
        (project / ".nac").mkdir()
        make_zip(
            project / ".nac/validate-only.zip",
            bundle_files({"schema.yaml": "a: str()\n", "rules/1.py": ""}, name="v"),
        )
        make_zip(
            project / ".nac/tests.zip",
            bundle_files({"tests/templates/a.robot": "x"}, name="t"),
        )

        result = invoke(dirs)

        assert result.exit_code == 0
        assert (kwargs_of(orchestrator_cls)["templates_dir"] / "a.robot").exists()

    def test_list_artifacts_names_each_bundle(
        self, project: Path, tmp_path: Path
    ) -> None:
        """Should label layers and templates with the bundle names."""
        a = self.bundle(tmp_path, "alpha", {"tests/templates/a.robot": "a"})
        b = self.bundle(
            tmp_path,
            "beta",
            {"tests/templates/b1.robot": "b", "tests/templates/b2.robot": "b"},
        )

        result = runner.invoke(
            app, ["--list-artifacts", "--bundle", str(a), "--bundle", str(b)]
        )

        assert result.exit_code == 0
        assert re.search(
            rf"1\.0\.0 \({re.escape(str(a))}.*\) \[bundle alpha\]", _plain(result)
        )
        assert "a.robot [bundle alpha]" in _plain(result)
        assert "b1.robot [bundle beta]" in _plain(result)
        assert "b2.robot [bundle beta]" in _plain(result)

    def test_list_artifacts_reports_overlapping_filters(
        self, project: Path, tmp_path: Path
    ) -> None:
        """Should fail with exit code 2 when two bundles provide the same filter."""
        files = {"tests/jinja_filters/f.py": FILTER.format(name="dup")}
        a = self.bundle(tmp_path, "alpha", files)
        b = self.bundle(tmp_path, "beta", files)

        result = runner.invoke(
            app, ["--list-artifacts", "--bundle", str(a), "--bundle", str(b)]
        )

        assert result.exit_code == EXIT_INVALID_ARGS
        assert "Filter 'dup' is provided by both" in _plain(result)
