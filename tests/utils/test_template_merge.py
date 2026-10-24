# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Daniel Schmidt

"""Unit tests for nac_test.utils.template_merge module.

Tests verify that templates from several layers are identified by relative
path, that the highest priority layer wins, and that the merged tree is a real
copy that never touches the source directories.
"""

from pathlib import Path

import pytest
from nac_artifacts import DisableEntry
from nac_artifacts.testing import write_files

from nac_test.core.constants import MERGED_TEMPLATES_DIRNAME
from nac_test.exceptions import TemplateError
from nac_test.utils.template_merge import (
    TemplateSource,
    effective_templates_dir,
    merge_template_dirs,
    plan_template_merge,
)


@pytest.fixture
def layers(tmp_path: Path) -> tuple[Path, Path]:
    """A local (high priority) and a module (low priority) template directory."""
    local = write_files(
        tmp_path / "local",
        {"config/a.robot": "local a", "only_local.robot": "local only"},
    )
    module = write_files(
        tmp_path / "module",
        {
            "config/a.robot": "module a",
            "config/b.robot": "module b",
            "lib/Utils.py": "# library",
            "common.resource": "module common",
        },
    )
    return local, module


class TestPlan:
    """Tests for deciding which file wins for every relative path."""

    def test_highest_priority_wins(self, layers: tuple[Path, Path]) -> None:
        """Should take a file from the highest priority source that has it."""
        local, module = layers

        plan = plan_template_merge([local, module])

        assert plan.files["config/a.robot"] == local.absolute() / "config/a.robot"
        assert plan.files["config/b.robot"] == module.absolute() / "config/b.robot"

    def test_union_of_all_relative_paths(self, layers: tuple[Path, Path]) -> None:
        """Should contain every relative path of every source once."""
        plan = plan_template_merge(list(layers))

        assert sorted(plan.files) == [
            "common.resource",
            "config/a.robot",
            "config/b.robot",
            "lib/Utils.py",
            "only_local.robot",
        ]

    def test_origins_and_shadowed_files(self, layers: tuple[Path, Path]) -> None:
        """Should record where each file came from and what was replaced."""
        local, module = layers

        plan = plan_template_merge([local, module])

        assert plan.origins["config/a.robot"] == local.absolute()
        assert plan.origins["config/b.robot"] == module.absolute()
        assert plan.shadowed == [
            ("config/a.robot", module.absolute(), local.absolute())
        ]

    def test_replacement_is_by_relative_path_not_file_name(
        self, tmp_path: Path
    ) -> None:
        """Should keep same-named files in different directories apart."""
        high = write_files(tmp_path / "high", {"x/a.robot": "high"})
        low = write_files(tmp_path / "low", {"y/a.robot": "low"})

        plan = plan_template_merge([high, low])

        assert sorted(plan.files) == ["x/a.robot", "y/a.robot"]
        assert plan.shadowed == []

    def test_three_layers(self, tmp_path: Path) -> None:
        """Should let each layer replace the ones below it."""
        top = write_files(tmp_path / "top", {"a.robot": "top"})
        mid = write_files(tmp_path / "mid", {"a.robot": "mid", "b.robot": "mid"})
        low = write_files(tmp_path / "low", {"a.robot": "low", "b.robot": "low"})

        plan = plan_template_merge([top, mid, low])

        assert plan.origins["a.robot"] == top.absolute()
        assert plan.origins["b.robot"] == mid.absolute()
        assert len(plan.shadowed) == 3

    def test_excluded_directories_inside_a_source_are_left_out(
        self, tmp_path: Path
    ) -> None:
        """Should skip excluded trees, e.g. Jinja filters kept inside templates."""
        source = write_files(
            tmp_path / "t", {"a.robot": "x", "filters/f.py": "# f", "keep/b.robot": "y"}
        )

        plan = plan_template_merge([source], exclude=[source / "filters"])

        assert sorted(plan.files) == ["a.robot", "keep/b.robot"]

    def test_exclusion_containing_the_source_does_not_hide_it(
        self, tmp_path: Path
    ) -> None:
        """Should ignore an excluded path that is above the source (output dir)."""
        source = write_files(tmp_path / "out" / "templates", {"a.robot": "x"})

        plan = plan_template_merge([source], exclude=[tmp_path / "out"])

        assert list(plan.files) == ["a.robot"]


class TestMerge:
    """Tests for building the merged copy."""

    def test_copies_content_of_the_winning_files(
        self, tmp_path: Path, layers: tuple[Path, Path]
    ) -> None:
        """Should write the winning file content, including non-template files."""
        target = tmp_path / "out" / "merged"

        merge_template_dirs(list(layers), target)

        assert (target / "config/a.robot").read_text() == "local a"
        assert (target / "config/b.robot").read_text() == "module b"
        assert (target / "lib/Utils.py").read_text() == "# library"
        assert (target / "only_local.robot").read_text() == "local only"

    def test_merged_files_are_real_copies(
        self, tmp_path: Path, layers: tuple[Path, Path]
    ) -> None:
        """Should not use symlinks, which break PyATS relative path handling."""
        target = tmp_path / "merged"

        merge_template_dirs(list(layers), target)

        assert not any(p.is_symlink() for p in target.rglob("*"))

    def test_sources_are_not_modified(
        self, tmp_path: Path, layers: tuple[Path, Path]
    ) -> None:
        """Should leave the source directories untouched."""
        local, module = layers
        before = sorted(p.relative_to(tmp_path).as_posix() for p in local.rglob("*"))

        merge_template_dirs([local, module], tmp_path / "merged")

        assert sorted(p.relative_to(tmp_path).as_posix() for p in local.rglob("*")) == (
            before
        )
        assert (module / "config/a.robot").read_text() == "module a"

    def test_stale_files_from_a_previous_merge_are_removed(
        self, tmp_path: Path, layers: tuple[Path, Path]
    ) -> None:
        """Should rebuild the target so removed templates do not linger."""
        target = write_files(tmp_path / "merged", {"stale.robot": "old"})

        merge_template_dirs(list(layers), target)

        assert not (target / "stale.robot").exists()

    def test_result_describes_the_merge(
        self, tmp_path: Path, layers: tuple[Path, Path]
    ) -> None:
        """Should return the root, origins and shadowed files."""
        result = merge_template_dirs(list(layers), tmp_path / "merged")

        assert result.root == (tmp_path / "merged").absolute()
        assert len(result.shadowed) == 1
        assert result.origins["config/b.robot"] == layers[1].absolute()

    def test_target_inside_a_source_is_not_copied_into_itself(
        self, tmp_path: Path
    ) -> None:
        """Should skip the target (e.g. an output directory below the templates)."""
        high = write_files(tmp_path / "high", {"a.robot": "x"})
        low = write_files(tmp_path / "low", {"b.robot": "y"})
        target = high / "out" / "merged"

        merge_template_dirs([high, low], target)
        merge_template_dirs([high, low], target)  # second run sees the first result

        assert sorted(
            p.relative_to(target).as_posix() for p in target.rglob("*.robot")
        ) == [
            "a.robot",
            "b.robot",
        ]

    @pytest.mark.parametrize("target_of", ["same", "parent"])
    def test_target_equal_to_or_above_a_source_is_rejected(
        self, tmp_path: Path, target_of: str
    ) -> None:
        """Should refuse to delete a directory that holds a template source."""
        source = write_files(tmp_path / "parent" / "src", {"a.robot": "x"})
        other = write_files(tmp_path / "other", {"b.robot": "y"})
        target = source if target_of == "same" else source.parent

        with pytest.raises(ValueError, match="must not be or contain"):
            merge_template_dirs([other, source], target)

        assert (source / "a.robot").exists()


class TestEffectiveTemplatesDir:
    """Tests for choosing between in-place use and a merged copy."""

    def test_no_sources(self, tmp_path: Path) -> None:
        """Should return None when no layer has templates."""
        assert effective_templates_dir([], tmp_path / "out") is None

    def test_single_source_is_used_in_place(self, tmp_path: Path) -> None:
        """Should not copy anything for a single template directory."""
        source = write_files(tmp_path / "t", {"a.robot": "x"})

        result = effective_templates_dir([source], tmp_path / "out")

        assert result == source
        assert not (tmp_path / "out").exists()

    def test_several_sources_are_merged_into_the_output_directory(
        self, tmp_path: Path, layers: tuple[Path, Path]
    ) -> None:
        """Should merge into a fixed subdirectory of the output directory."""
        result = effective_templates_dir(list(layers), tmp_path / "out")

        assert result == (tmp_path / "out" / MERGED_TEMPLATES_DIRNAME).absolute()
        assert (result / "config/b.robot").read_text() == "module b"

    def test_exclusions_are_passed_on(self, tmp_path: Path) -> None:
        """Should leave excluded directories out of the merged copy."""
        high = write_files(tmp_path / "high", {"a.robot": "x", "filters/f.py": "# f"})
        low = write_files(tmp_path / "low", {"b.robot": "y"})

        result = effective_templates_dir(
            [high, low], tmp_path / "out", exclude=[high / "filters"]
        )

        assert result is not None
        assert not (result / "filters").exists()
        assert (result / "a.robot").exists()


def project_entry(pattern: str) -> DisableEntry:
    return DisableEntry(pattern, "project")


def src(path: Path, *patterns: str, tier: str = "", label: str = "") -> TemplateSource:
    """A template source with optional disable entries from the project."""
    return TemplateSource(
        path, tuple(project_entry(p) for p in patterns), tier=tier, label=label
    )


class TestDisabledTemplates:
    """Tests for removing templates of lower layers with overrides.yaml entries."""

    def test_matching_files_are_removed_from_that_source(
        self, layers: tuple[Path, Path]
    ) -> None:
        """Should drop a module template whose path matches an entry."""
        local, module = layers

        plan = plan_template_merge([local, src(module, "config/b.robot")])

        assert "config/b.robot" not in plan.files
        assert [(rel, s_, e.pattern) for rel, s_, e in plan.disabled] == [
            ("config/b.robot", module.absolute(), "config/b.robot")
        ]

    def test_globs_cover_nested_files(self, layers: tuple[Path, Path]) -> None:
        """Should let a glob such as lib/* remove everything below lib/."""
        _, module = layers

        plan = plan_template_merge([src(module, "lib/*")])

        assert "lib/Utils.py" not in plan.files
        assert "common.resource" in plan.files

    def test_higher_layer_file_at_the_same_path_still_wins(
        self, layers: tuple[Path, Path]
    ) -> None:
        """Should only remove the lower layer's file, never the higher layer's."""
        local, module = layers

        plan = plan_template_merge([local, src(module, "config/a.robot")])

        assert plan.files["config/a.robot"] == local.absolute() / "config/a.robot"
        assert plan.shadowed == []  # the module file was removed, not shadowed

    def test_entries_for_one_source_do_not_touch_another(
        self, layers: tuple[Path, Path]
    ) -> None:
        """Should apply entries only to the source they were given for."""
        local, module = layers

        plan = plan_template_merge([local, src(module, "only_local.robot")])

        assert "only_local.robot" in plan.files

    def test_entries_matching_nothing_are_listed_not_raised(
        self, layers: tuple[Path, Path]
    ) -> None:
        """Should report entries that matched no template in any source."""
        local, module = layers

        plan = plan_template_merge([local, src(module, "config/b.robot", "nope/*")])

        assert [e.pattern for e in plan.unmatched] == ["nope/*"]

    def test_entry_matching_in_one_source_is_not_unmatched(
        self, layers: tuple[Path, Path]
    ) -> None:
        """Should call an entry unmatched only if it matched nowhere."""
        local, module = layers

        plan = plan_template_merge(
            [src(local, "config/b.robot"), src(module, "config/b.robot")]
        )

        assert plan.unmatched == []

    def test_plain_paths_are_accepted(self, layers: tuple[Path, Path]) -> None:
        """Should treat plain paths as sources without entries."""
        plan = plan_template_merge(list(layers))

        assert plan.disabled == []

    def test_disabled_files_are_not_copied(
        self, tmp_path: Path, layers: tuple[Path, Path]
    ) -> None:
        """Should leave disabled templates out of the merged tree."""
        local, module = layers
        target = tmp_path / "merged"

        result = merge_template_dirs([local, src(module, "lib/*")], target)

        assert not (target / "lib").exists()
        assert (target / "config/b.robot").exists()
        assert [rel for rel, _, _ in result.disabled] == ["lib/Utils.py"]

    def test_single_source_with_a_match_is_merged_not_used_in_place(
        self, tmp_path: Path
    ) -> None:
        """Should make a copy when a disabled file must disappear from a lone source."""
        source = write_files(tmp_path / "t", {"a.robot": "x", "b.robot": "y"})

        result = effective_templates_dir([src(source, "b.robot")], tmp_path / "out")

        assert result == (tmp_path / "out" / MERGED_TEMPLATES_DIRNAME).absolute()
        assert (result / "a.robot").exists()
        assert not (result / "b.robot").exists()

    def test_single_source_without_a_match_stays_in_place(self, tmp_path: Path) -> None:
        """Should not copy when entries exist but match nothing."""
        source = write_files(tmp_path / "t", {"a.robot": "x"})

        result = effective_templates_dir([src(source, "zzz")], tmp_path / "out")

        assert result == source
        assert not (tmp_path / "out").exists()


class TestPeerSources:
    """Sources of one tier (several bundles) may split templates but not overlap."""

    @pytest.fixture
    def peers(self, tmp_path: Path) -> tuple[Path, Path]:
        a = write_files(tmp_path / "a", {"one.robot": "a1", "shared/x.robot": "a"})
        b = write_files(tmp_path / "b", {"two.robot": "b2", "shared/y.robot": "b"})
        return a, b

    def test_disjoint_peers_are_combined(self, peers: tuple[Path, Path]) -> None:
        """Should merge peers that provide different relative paths."""
        a, b = peers

        plan = plan_template_merge(
            [
                src(a, tier="bundle", label="bundle a"),
                src(b, tier="bundle", label="bundle b"),
            ]
        )

        assert sorted(plan.files) == [
            "one.robot",
            "shared/x.robot",
            "shared/y.robot",
            "two.robot",
        ]
        assert plan.shadowed == []

    def test_overlapping_peers_raise_naming_both(
        self, tmp_path: Path, peers: tuple[Path, Path]
    ) -> None:
        """Should refuse a path two peers provide, naming the path and both bundles."""
        a, b = peers
        write_files(b, {"one.robot": "clash"})

        with pytest.raises(
            TemplateError, match="'one.robot' is provided by both bundle a and bundle b"
        ):
            plan_template_merge(
                [
                    src(a, tier="bundle", label="bundle a"),
                    src(b, tier="bundle", label="bundle b"),
                ]
            )

    def test_overlap_message_falls_back_to_the_path_without_labels(
        self, peers: tuple[Path, Path]
    ) -> None:
        """Should still say where the templates are when no label was given."""
        a, b = peers
        write_files(b, {"one.robot": "clash"})

        with pytest.raises(TemplateError, match="provided by both .*a and .*b"):
            plan_template_merge([src(a, tier="bundle"), src(b, tier="bundle")])

    def test_untiered_sources_are_never_peers(self, peers: tuple[Path, Path]) -> None:
        """Should treat plain sources as ordered layers, where the first one wins."""
        a, b = peers
        write_files(b, {"one.robot": "from b"})

        plan = plan_template_merge([a, b])

        assert plan.files["one.robot"] == a.absolute() / "one.robot"

    def test_different_tiers_are_ordered_not_peers(
        self, peers: tuple[Path, Path]
    ) -> None:
        """Should let a higher tier replace a lower one with the same path."""
        a, b = peers
        write_files(b, {"one.robot": "from module"})

        plan = plan_template_merge(
            [
                src(a, tier="bundle", label="bundle a"),
                src(b, tier="module", label="module"),
            ]
        )

        assert plan.files["one.robot"] == a.absolute() / "one.robot"
        assert [(rel, lo) for rel, lo, _ in plan.shadowed] == [
            ("one.robot", b.absolute())
        ]

    def test_peers_are_both_above_the_lower_tier(
        self, tmp_path: Path, peers: tuple[Path, Path]
    ) -> None:
        """Should let each peer replace the module's file at its own paths."""
        a, b = peers
        module = write_files(
            tmp_path / "m", {"one.robot": "m1", "two.robot": "m2", "only.robot": "m"}
        )

        plan = plan_template_merge(
            [
                src(a, tier="bundle", label="bundle a"),
                src(b, tier="bundle", label="bundle b"),
                src(module, tier="module", label="module"),
            ]
        )

        assert plan.origins["one.robot"] == a.absolute()
        assert plan.origins["two.robot"] == b.absolute()
        assert plan.origins["only.robot"] == module.absolute()

    def test_a_disabled_template_is_not_an_overlap(
        self, peers: tuple[Path, Path]
    ) -> None:
        """Should drop disabled files before looking for overlaps."""
        a, b = peers
        write_files(b, {"one.robot": "clash"})

        plan = plan_template_merge(
            [src(a, tier="bundle"), src(b, "one.robot", tier="bundle")]
        )

        assert plan.origins["one.robot"] == a.absolute()

    def test_merged_copy_contains_all_peers(
        self, tmp_path: Path, peers: tuple[Path, Path]
    ) -> None:
        """Should copy the templates of every peer."""
        a, b = peers

        result = effective_templates_dir(
            [src(a, tier="bundle"), src(b, tier="bundle")], tmp_path / "out"
        )

        assert result is not None
        assert (result / "one.robot").read_text() == "a1"
        assert (result / "two.robot").read_text() == "b2"
