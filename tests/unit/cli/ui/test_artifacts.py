# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Daniel Schmidt

"""Unit tests for nac_test.cli.ui.artifacts module."""

from pathlib import Path
from typing import Any

import pytest
from nac_artifacts import DisableEntry

from nac_test.cli.ui.artifacts import format_artifacts_list
from nac_test.layers import AssetLayer
from nac_test.robot.jinja_extensions import LoadedExtension
from nac_test.utils.template_merge import TemplatePlan
from nac_test.utils.terminal import TerminalColors

LOCAL = Path("/p/local").absolute()
MODULE = Path("/p/module").absolute()
LOCAL_FILTERS = Path("/p/local-filters").absolute()
MODULE_FILTERS = Path("/p/module-filters").absolute()


def layers() -> list[AssetLayer]:
    return [
        AssetLayer("local", LOCAL, LOCAL_FILTERS, None, detail="templates /p/local"),
        AssetLayer(
            "module", MODULE, MODULE_FILTERS, None, "1.0.0", "module 'nxos' 1.0.0"
        ),
    ]


def format_plain(*args: Any) -> str:
    """Format without ANSI styles."""
    return TerminalColors.strip_ansi(format_artifacts_list(*args))


def plan() -> TemplatePlan:
    return TemplatePlan(
        files={"a.robot": LOCAL / "a.robot", "b.robot": MODULE / "b.robot"},
        origins={"a.robot": LOCAL, "b.robot": MODULE},
        shadowed=[("a.robot", MODULE, LOCAL)],
    )


class TestFormatArtifactsList:
    """Tests for the --list-artifacts output."""

    def test_layers_are_listed_in_priority_order(self) -> None:
        """Should print every layer with its origin and description."""
        text = format_plain(layers(), plan(), {}, {})

        assert text.index("  templates /p/local [local]") < text.index(
            "  module 'nxos' 1.0.0 [module]"
        )

    def test_empty_local_layer_is_left_out(self) -> None:
        """Should not list a local layer without any path, like an absent bundle."""
        empty = [AssetLayer("local", None, None, None), layers()[1]]

        text = format_plain(empty, plan(), {}, {})

        assert "[local]" not in text.split("Templates:")[0]
        assert "  module 'nxos' 1.0.0 [module]" in text

    def test_no_layers(self) -> None:
        """Should say there are none."""
        text = format_plain(
            [AssetLayer("local", None, None, None)], TemplatePlan(), {}, {}
        )

        assert "Artifact Layers (highest priority first):\n  none" in text

    def test_every_template_is_listed_with_its_layer(self) -> None:
        """Should list each effective template, sorted, tagged with its layer."""
        text = format_plain(layers(), plan(), {}, {})

        assert text.index("  a.robot [local]") < text.index("  b.robot [module]")
        assert "Total: 2 templates" in text

    def test_shadowed_layers_are_listed_in_priority_order(self) -> None:
        """Should name every lower layer a template shadows, highest first."""
        bundle = Path("/p/bundle").absolute()
        three = [
            layers()[0],
            AssetLayer("bundle", bundle, None, None, label="bundle acme"),
            layers()[1],
        ]
        shadowing = TemplatePlan(
            files={"a.robot": LOCAL / "a.robot"},
            origins={"a.robot": LOCAL},
            shadowed=[("a.robot", MODULE, bundle), ("a.robot", bundle, LOCAL)],
        )

        text = format_plain(three, shadowing, {}, {})

        assert "a.robot [local] shadows [bundle acme], [module]" in text

    def test_styled_like_nac_validate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should use bright cyan headings and magenta labels unless NO_COLOR is set."""
        styled = format_artifacts_list(layers(), plan(), {}, {})
        monkeypatch.setattr(TerminalColors, "NO_COLOR", True)
        plain = format_artifacts_list(layers(), plan(), {}, {})

        assert "\x1b[96m\x1b[1mTemplates:" in styled
        assert "\x1b[95m[module]\x1b[0m" in styled
        assert "\n  \x1b[95m[" not in styled  # labels never lead a line
        assert "\x1b[" not in plain

    def test_no_templates(self) -> None:
        """Should say there are none."""
        text = format_plain(layers(), TemplatePlan(), {}, {})

        assert "Templates:\n  none" in text

    def test_filters_and_tests_show_their_origin(self) -> None:
        """Should list names sorted, tagged with the layer they came from."""
        filters = {
            "zeta": LoadedExtension(object, MODULE_FILTERS),
            "alpha": LoadedExtension(object, LOCAL_FILTERS),
        }

        text = format_plain(layers(), plan(), filters, {})

        assert text.index("alpha [local]") < text.index("zeta [module]")
        assert "Jinja Tests:\n  none" in text

    def test_disabled_templates_show_origin_and_source(self) -> None:
        """Should list each disabled template, its layer and who disabled it."""
        entry = DisableEntry("lib/*", "project")
        plan = TemplatePlan(disabled=[("lib/Utils.py", MODULE, entry)])

        text = format_plain(layers(), plan, {}, {})

        assert "Disabled Templates:" in text
        assert "lib/Utils.py [module] disabled by project overrides" in text

    def test_unmatched_entries_are_listed(self) -> None:
        """Should report entries that matched no template."""
        plan = TemplatePlan(unmatched=[DisableEntry("nope/*", "bundle")])

        text = format_plain(layers(), plan, {}, {})

        assert "Overrides Matching No Template:" in text
        assert "nope/* ([bundle] overrides)" in text

    def test_no_disable_sections_without_entries(self) -> None:
        """Should leave the output unchanged when nothing is disabled."""
        text = format_plain(layers(), plan(), {}, {})

        assert "Disabled Templates" not in text
        assert "Matching No Template" not in text
