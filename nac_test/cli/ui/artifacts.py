# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Daniel Schmidt

"""Formatting of the effective templates, filters and Jinja tests.

The layout matches ``nac-validate --list-artifacts``: every line names the item
first and the layer label (``[local]``, ``[bundle <name>]``, ``[module]``) after
it, always in the same style.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import typer

from nac_test.layers import AssetLayer
from nac_test.robot.jinja_extensions import LoadedExtension
from nac_test.utils.template_merge import TemplatePlan
from nac_test.utils.terminal import TerminalColors

SEPARATOR_WIDTH = 80


def _style(text: str, **styles: Any) -> str:
    """Style text unless NO_COLOR is set."""
    return text if TerminalColors.NO_COLOR else typer.style(text, **styles)


def _heading(text: str) -> str:
    return _style(f"{text}:", fg="bright_cyan", bold=True)


def _dim(text: str) -> str:
    return _style(text, dim=True)


def _none() -> str:
    return "  " + _style("none", fg="bright_yellow")


def _owners(layers: Sequence[AssetLayer]) -> dict[Path, str]:
    """Map every layer directory to the tag of its layer."""
    owners: dict[Path, str] = {}
    for layer in layers:
        for path in (layer.templates, layer.filters, layer.jinja_tests):
            if path is not None:
                owners[path.absolute()] = layer.tag
    return owners


def _label(tag: str) -> str:
    """Render a layer label; every label in the listing looks the same."""
    return _style(f"[{tag}]", fg="bright_magenta")


def _origin(tag: str, shadows: Sequence[str] = ()) -> str:
    """Render ``[tag]`` plus the lower layers it shadows, highest priority first."""
    text = _label(tag)
    if shadows:
        text += f" {_dim('shadows')} " + f"{_dim(',')} ".join(
            _label(s) for s in shadows
        )
    return text


def _overrides(source: str) -> str:
    """Render who an overrides.yaml entry came from: the project or a bundle label."""
    if source == "project":
        return _dim("project overrides")
    return f"{_label(source)} {_dim('overrides')}"


def _templates(
    layers: Sequence[AssetLayer], plan: TemplatePlan, owners: Mapping[Path, str]
) -> list[str]:
    """List every effective template with its layer and the layers it shadows."""
    lines = ["", _heading("Templates")]
    if not plan.origins:
        return [*lines, _none()]
    lines.append(_dim("─" * SEPARATOR_WIDTH))
    priority = {layer.tag: i for i, layer in enumerate(layers)}
    shadows: dict[str, list[str]] = {}
    for rel, shadowed, _ in plan.shadowed:
        shadows.setdefault(rel, []).append(owners.get(shadowed, "?"))
    lines.append("")
    for rel, origin in sorted(plan.origins.items()):
        lower = sorted(shadows.get(rel, []), key=lambda t: priority.get(t, len(layers)))
        lines.append(f"  {rel} {_origin(owners.get(origin, '?'), lower)}")
    lines.append("")
    lines.append(_dim("─" * SEPARATOR_WIDTH))
    lines.append(_dim(f"Total: {len(plan.origins)} templates"))
    return lines


def _disabled_templates(plan: TemplatePlan, owners: Mapping[Path, str]) -> list[str]:
    """Format templates removed by overrides.yaml and entries that matched nothing."""
    lines: list[str] = []
    if plan.disabled:
        lines += ["", _heading("Disabled Templates")]
        for rel, source, entry in sorted(plan.disabled, key=lambda d: d[0]):
            lines.append(
                f"  {rel} {_label(owners.get(source, '?'))} "
                f"{_dim('disabled by')} {_overrides(entry.source)}"
            )
    if plan.unmatched:
        lines += ["", _heading("Overrides Matching No Template")]
        lines += [
            f"  {e.pattern} {_dim('(')}{_overrides(e.source)}{_dim(')')}"
            for e in plan.unmatched
        ]
    return lines


def _extensions(
    title: str,
    extensions: Mapping[str, LoadedExtension],
    owners: Mapping[Path, str],
) -> list[str]:
    lines = ["", _heading(title)]
    if not extensions:
        return [*lines, _none()]
    for name, extension in sorted(extensions.items()):
        lines.append(
            f"  {name} {_origin(owners.get(extension.origin.absolute(), '?'))}"
        )
    return lines


def format_artifacts_list(
    layers: Sequence[AssetLayer],
    plan: TemplatePlan,
    filters: Mapping[str, LoadedExtension],
    jinja_tests: Mapping[str, LoadedExtension],
) -> str:
    """Format layers, effective templates, Jinja filters and Jinja tests.

    Args:
        layers: Resolved layers, highest priority first.
        plan: Which source provides each template.
        filters: Loaded Jinja filters by name.
        jinja_tests: Loaded Jinja tests by name.
    """
    owners = _owners(layers)
    lines = ["", _heading("Artifact Layers (highest priority first)")]
    shown = [layer for layer in layers if not layer.is_empty]
    lines += [f"  {layer.detail} {_label(layer.tag)}" for layer in shown] or [_none()]
    lines += _templates(layers, plan, owners)
    lines += _disabled_templates(plan, owners)
    lines += _extensions("Jinja Filters", filters, owners)
    lines += _extensions("Jinja Tests", jinja_tests, owners)
    return "\n".join(lines) + "\n"
