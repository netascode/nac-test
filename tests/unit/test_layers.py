# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Daniel Schmidt

"""Unit tests for nac_test.layers module.

Tests verify the local layer and the mapping of bundle and module layers to
the templates, Jinja filters and Jinja tests nac-test reads from them.
"""

from pathlib import Path

import pytest
from nac_artifacts import (
    ArtifactError,
    BundleError,
    DisableEntry,
    ModuleDiscoveryError,
    OverridesError,
)
from nac_artifacts.testing import (
    bundle_files,
    install_module,
    make_zip,
    module_entry,
    overrides_yaml,
    write_files,
    write_modules_json,
)

from nac_test.layers import (
    AssetLayer,
    directories,
    extension_tiers,
    resolve_layers,
    template_sources,
)
from nac_test.utils.template_merge import TemplateSource

TEMPLATES = {"tests/templates/a.robot": "*** Test Cases ***\n"}
FILTERS = {"tests/jinja_filters/f.py": "# filter\n"}
JINJA_TESTS = {"tests/jinja_tests/t.py": "# test\n"}


class TestLocalLayer:
    """Tests for the local layer built from the command line options."""

    def test_local_layer_is_always_first(self, project: Path) -> None:
        """Should return only the local layer when nothing else is found."""
        layers = resolve_layers(project)

        assert [layer.origin for layer in layers] == ["local"]

    def test_options_are_carried_over(self, project: Path) -> None:
        """Should keep the paths given with -t, -f and --tests."""
        layer = resolve_layers(
            project,
            templates=Path("t"),
            filters=Path("f"),
            jinja_tests=Path("j"),
        )[0]

        assert (layer.templates, layer.filters, layer.jinja_tests) == (
            Path("t"),
            Path("f"),
            Path("j"),
        )

    def test_detail_lists_only_the_given_paths(self, project: Path) -> None:
        """Should describe just the options that were given."""
        detail = resolve_layers(project, templates=Path("t"), jinja_tests=Path("j"))[
            0
        ].detail

        assert detail == "templates t, tests j"

    def test_without_any_option_the_layer_is_empty(self, project: Path) -> None:
        """Should describe nothing and report the layer as empty."""
        local = resolve_layers(project)[0]

        assert local.detail == ""
        assert local.is_empty


class TestPackagedLayers:
    """Tests for how bundle and module layers map to nac-test directories."""

    def test_module_directories_are_mapped(self, project: Path) -> None:
        """Should expose the module's templates, filters and Jinja tests."""
        module_dir = install_module(
            project, {**TEMPLATES, **FILTERS, **JINJA_TESTS}, version="0.3.0"
        )

        module = resolve_layers(project)[1]

        nac_dir = module_dir.resolve() / "nac"
        assert module.origin == "module"
        assert module.templates == nac_dir / "tests/templates"
        assert module.filters == nac_dir / "tests/jinja_filters"
        assert module.jinja_tests == nac_dir / "tests/jinja_tests"
        assert module.version == "0.3.0"

    def test_missing_directories_are_none(self, project: Path) -> None:
        """Should leave directories the module does not ship empty."""
        install_module(project, TEMPLATES)

        module = resolve_layers(project)[1]

        assert module.templates is not None
        assert module.filters is None
        assert module.jinja_tests is None

    def test_module_without_test_artifacts_is_not_used(self, project: Path) -> None:
        """Should ignore a module that only ships a schema and rules."""
        install_module(project, {"schema.yaml": "a: str()\n", "rules/1.py": ""})

        assert [layer.origin for layer in resolve_layers(project)] == ["local"]

    def test_layer_order_is_local_bundle_module(
        self, project: Path, tmp_path: Path
    ) -> None:
        """Should order layers local, bundle, module (highest priority first)."""
        install_module(project, TEMPLATES)
        archive = make_zip(tmp_path / "b.zip", bundle_files(TEMPLATES))

        layers = resolve_layers(project, bundles=[archive])

        assert [layer.origin for layer in layers] == ["local", "bundle", "module"]

    def test_bundle_directories_are_mapped(self, project: Path, tmp_path: Path) -> None:
        """Should map a bundle like a module, including its manifest version."""
        archive = make_zip(
            tmp_path / "acme-1.2.0.zip",
            bundle_files({**TEMPLATES, **FILTERS}, version="1.2.0"),
        )

        bundle = resolve_layers(project, bundles=[archive])[1]

        assert bundle.origin == "bundle"
        assert bundle.version == "1.2.0"
        assert bundle.templates is not None and bundle.templates.is_dir()
        assert bundle.filters is not None and bundle.filters.is_dir()

    def test_explicit_module_dir(self, project: Path, tmp_path: Path) -> None:
        """Should use --module-dir without reading modules.json."""
        write_files(tmp_path / "mod/nac", TEMPLATES)

        layers = resolve_layers(project, module_dir=tmp_path / "mod")

        assert layers[1].templates == (tmp_path / "mod").resolve() / (
            "nac/tests/templates"
        )


class TestErrors:
    """Tests for failures while resolving packaged layers."""

    def test_ambiguous_modules_point_to_the_cli_option(self, project: Path) -> None:
        """Should tell CLI users to select a module with --module-dir."""
        for key in ("a", "b"):
            write_files(project / f".terraform/modules/{key}/nac", TEMPLATES)
        write_modules_json(
            project, [module_entry(k, f".terraform/modules/{k}") for k in ("a", "b")]
        )

        with pytest.raises(ModuleDiscoveryError, match="Use --module-dir"):
            resolve_layers(project)

    def test_bundle_errors_propagate(self, project: Path, tmp_path: Path) -> None:
        """Should raise the library's error for a bundle that does not exist."""
        with pytest.raises(BundleError, match="not found"):
            resolve_layers(project, bundles=[tmp_path / "missing.zip"])

    def test_all_errors_share_a_base_class(self, project: Path, tmp_path: Path) -> None:
        """Should let callers catch every discovery failure with one type."""
        with pytest.raises(ArtifactError):
            resolve_layers(project, bundles=[tmp_path / "missing.zip"])


class TestDirectories:
    """Tests for collecting one kind of directory from the layers."""

    @staticmethod
    def layer(origin: str, templates: str | None, filters: str | None) -> AssetLayer:
        return AssetLayer(
            origin=origin,  # type: ignore[arg-type]
            templates=Path(templates) if templates else None,
            filters=Path(filters) if filters else None,
            jinja_tests=None,
        )

    def test_keeps_priority_order_and_skips_missing(self) -> None:
        """Should return the existing directories in layer order."""
        layers = [
            self.layer("local", "lt", None),
            self.layer("bundle", None, "bf"),
            self.layer("module", "mt", "mf"),
        ]

        assert directories(layers, "templates") == [Path("lt"), Path("mt")]
        assert directories(layers, "filters") == [Path("bf"), Path("mf")]
        assert directories(layers, "jinja_tests") == []


class TestDisabledTemplates:
    """Tests for which disable entries reach which layer."""

    @staticmethod
    def write_project_overrides(project: Path, **kwargs: list[str]) -> None:
        write_files(project / ".nac", {"overrides.yaml": overrides_yaml(**kwargs)})

    def test_local_layer_is_never_affected(self, project: Path) -> None:
        """Should keep the local templates out of reach of any disable entry."""
        install_module(project, TEMPLATES)
        self.write_project_overrides(project, templates=["a.robot"])

        assert resolve_layers(project, templates=Path("t"))[0].disabled_templates == ()

    def test_project_entries_reach_bundle_and_module(
        self, project: Path, tmp_path: Path
    ) -> None:
        """Should apply .nac/overrides.yaml to every packaged layer."""
        install_module(project, TEMPLATES)
        archive = make_zip(tmp_path / "b.zip", bundle_files(TEMPLATES))
        self.write_project_overrides(project, templates=["lib/*"])

        _, bundle, module = resolve_layers(project, bundles=[archive])

        expected = (DisableEntry("lib/*", "project"),)
        assert bundle.disabled_templates == expected
        assert module.disabled_templates == expected

    def test_bundle_entries_reach_only_the_module(
        self, project: Path, tmp_path: Path
    ) -> None:
        """Should apply a bundle's overrides.yaml to the module below it."""
        install_module(project, TEMPLATES)
        archive = make_zip(
            tmp_path / "b.zip",
            bundle_files(
                TEMPLATES,
                extra={"overrides.yaml": overrides_yaml(templates=["x.robot"])},
            ),
        )

        _, bundle, module = resolve_layers(project, bundles=[archive])

        assert bundle.disabled_templates == ()
        assert module.disabled_templates == (DisableEntry("x.robot", "bundle acme"),)

    def test_rule_entries_are_ignored(self, project: Path) -> None:
        """Should ignore rule entries, which only nac-validate uses."""
        install_module(project, TEMPLATES)
        self.write_project_overrides(project, rules=["102"])

        assert resolve_layers(project)[1].disabled_templates == ()

    def test_malformed_overrides_raise(self, project: Path) -> None:
        """Should fail instead of ignoring a broken overrides file."""
        install_module(project, TEMPLATES)
        write_files(project / ".nac", {"overrides.yaml": "- x\n"})

        with pytest.raises(OverridesError):
            resolve_layers(project)

    def test_template_sources_line_up_with_template_directories(self) -> None:
        """Should skip layers without templates so lists stay aligned."""
        entry = DisableEntry("a", "project")
        layers = [
            AssetLayer("local", Path("lt"), None, None),
            AssetLayer("bundle", None, Path("bf"), None, disabled_templates=(entry,)),
            AssetLayer(
                "module",
                Path("mt"),
                None,
                None,
                disabled_templates=(entry,),
                label="module",
            ),
        ]

        assert directories(layers, "templates") == [Path("lt"), Path("mt")]
        assert template_sources(layers) == [
            TemplateSource(Path("lt"), (), tier="local", label="local"),
            TemplateSource(Path("mt"), (entry,), tier="module", label="module"),
        ]


class TestMultipleBundleLayers:
    """Several bundles are peers sharing one tier."""

    @staticmethod
    def two_bundles(tmp_path: Path) -> list[Path]:
        return [
            make_zip(
                tmp_path / f"{name}.zip",
                bundle_files({f"tests/templates/{name}.robot": "x"}, name=name),
            )
            for name in ("alpha", "beta")
        ]

    def test_every_bundle_becomes_a_layer_with_its_name(
        self, project: Path, tmp_path: Path
    ) -> None:
        """Should label bundle layers by manifest name."""
        layers = resolve_layers(project, bundles=self.two_bundles(tmp_path))

        assert [layer.tag for layer in layers] == [
            "local",
            "bundle alpha",
            "bundle beta",
        ]

    def test_bundles_share_a_tier_in_the_template_sources(
        self, project: Path, tmp_path: Path
    ) -> None:
        """Should mark both bundles as peers so overlaps are detected."""
        layers = resolve_layers(project, bundles=self.two_bundles(tmp_path))

        tiers = [(src.tier, src.label) for src in template_sources(layers)]

        assert tiers == [("bundle", "bundle alpha"), ("bundle", "bundle beta")]

    def test_extension_tiers_group_bundle_directories(
        self, project: Path, tmp_path: Path
    ) -> None:
        """Should return one tier of peers for the bundles and one for the module."""
        archives = [
            make_zip(
                tmp_path / f"{name}.zip",
                bundle_files({f"tests/jinja_filters/{name}.py": "# f"}, name=name),
            )
            for name in ("alpha", "beta")
        ]
        install_module(project, {"tests/jinja_filters/m.py": "# f"})

        layers = resolve_layers(project, bundles=archives, filters=Path("lf"))
        tiers = extension_tiers(layers, "filters")

        assert tiers[0] == Path("lf")
        assert isinstance(tiers[1], list) and len(tiers[1]) == 2
        assert isinstance(tiers[2], Path)

    def test_extension_tiers_without_directories(self) -> None:
        """Should return nothing when no layer has the directory."""
        layers = [AssetLayer("local", Path("t"), None, None)]

        assert extension_tiers(layers, "filters") == []

    def test_bundle_overrides_do_not_reach_a_peer(
        self, project: Path, tmp_path: Path
    ) -> None:
        """Should keep a bundle's disable entries for the module only."""
        install_module(project, TEMPLATES)
        a = make_zip(
            tmp_path / "a.zip",
            bundle_files(
                TEMPLATES,
                name="a",
                extra={"overrides.yaml": overrides_yaml(templates=["x.robot"])},
            ),
        )
        b = make_zip(tmp_path / "b.zip", bundle_files(TEMPLATES, name="b"))

        _, layer_a, layer_b, module = resolve_layers(project, bundles=[a, b])

        assert layer_a.disabled_templates == layer_b.disabled_templates == ()
        assert [(e.pattern, e.source) for e in module.disabled_templates] == [
            ("x.robot", "bundle a")
        ]
