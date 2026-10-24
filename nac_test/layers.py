# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Daniel Schmidt

"""Template, filter and Jinja test layers used by nac-test.

Templates, Jinja filters and Jinja tests come from up to three layers, highest
priority first:

1. local:  the ``-t``/``-f``/``--tests`` options
2. bundles: archives or directories dropped into the project (``.nac/``); several
   bundles are peers that may split artifacts but must not overlap
3. module: the ``nac/`` directory embedded in an installed Terraform module

The bundle and module layers are located by :mod:`nac_artifacts`; this module
adds the local layer and maps each layer to the directories nac-test reads.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from nac_artifacts import (
    AmbiguousModuleError,
    ArtifactLayer,
    DisableEntry,
    LayerDisables,
    ModuleDiscoveryError,
    layer_disables,
    resolve_artifact_layers,
)

from nac_test.core.constants import (
    ARTIFACTS_FILTERS_PATH,
    ARTIFACTS_JINJA_TESTS_PATH,
    ARTIFACTS_TEMPLATES_PATH,
)
from nac_test.utils.template_merge import TemplateSource

logger = logging.getLogger(__name__)

Origin = Literal["local", "bundle", "module"]


@dataclass(frozen=True)
class AssetLayer:
    """One source of templates, Jinja filters and Jinja tests.

    Attributes:
        origin: Which layer this is (local, bundle or module).
        templates: Directory with test templates provided by this layer, if any.
        filters: Directory with Jinja filters provided by this layer, if any.
        jinja_tests: Directory with Jinja tests provided by this layer, if any.
        version: Module version or bundle manifest version, if known.
        detail: Human-readable description of where the layer came from.
        disabled_templates: Entries (relative paths or globs) that disable
            templates of this layer, from ``.nac/overrides.yaml`` and from
            bundles above it.
        label: Name for messages, e.g. ``bundle acme-base`` (defaults to the origin).
    """

    origin: Origin
    templates: Path | None
    filters: Path | None
    jinja_tests: Path | None
    version: str | None = None
    detail: str = ""
    disabled_templates: tuple[DisableEntry, ...] = ()
    label: str = ""

    @property
    def tag(self) -> str:
        """Label used in output and messages."""
        return self.label or self.origin

    @property
    def is_empty(self) -> bool:
        """Whether the layer provides no templates, filters or Jinja tests."""
        return (
            self.templates is None and self.filters is None and self.jinja_tests is None
        )


def _describe(label: str, path: Path | None) -> str | None:
    """Render ``label path`` for an option that was given, else None."""
    return None if path is None else f"{label} {path}"


def _local_layer(
    templates: Path | None, filters: Path | None, jinja_tests: Path | None
) -> AssetLayer:
    """Build the local layer from the command line options."""
    given = [
        text
        for text in (
            _describe("templates", templates),
            _describe("filters", filters),
            _describe("tests", jinja_tests),
        )
        if text is not None
    ]
    return AssetLayer(
        origin="local",
        templates=templates,
        filters=filters,
        jinja_tests=jinja_tests,
        detail=", ".join(given),
    )


def _from_artifact_layer(layer: ArtifactLayer, disables: LayerDisables) -> AssetLayer:
    """Map a bundle or module layer to the directories it provides."""
    templates = layer.nac_dir / ARTIFACTS_TEMPLATES_PATH
    filters = layer.nac_dir / ARTIFACTS_FILTERS_PATH
    jinja_tests = layer.nac_dir / ARTIFACTS_JINJA_TESTS_PATH
    return AssetLayer(
        origin=layer.origin,
        templates=templates if templates.is_dir() else None,
        filters=filters if filters.is_dir() else None,
        jinja_tests=jinja_tests if jinja_tests.is_dir() else None,
        version=layer.version,
        detail=layer.detail,
        disabled_templates=disables.templates,
        label=layer.label,
    )


def resolve_layers(
    project_dir: Path,
    *,
    templates: Path | None = None,
    filters: Path | None = None,
    jinja_tests: Path | None = None,
    bundles: Sequence[Path] | None = None,
    module_dir: Path | None = None,
) -> list[AssetLayer]:
    """Resolve all template, filter and Jinja test layers, highest priority first.

    Raises:
        nac_artifacts.ArtifactError: If a bundle or module cannot be resolved.
    """
    local = _local_layer(templates, filters, jinja_tests)
    logger.info("Artifact layer [%s]: %s", local.origin, local.detail)
    try:
        artifact_layers = resolve_artifact_layers(
            project_dir,
            provides=(
                ARTIFACTS_TEMPLATES_PATH,
                ARTIFACTS_FILTERS_PATH,
                ARTIFACTS_JINJA_TESTS_PATH,
            ),
            bundles=bundles,
            module_dir=module_dir,
        )
    except AmbiguousModuleError as e:
        raise ModuleDiscoveryError(f"{e} Use --module-dir to select one.") from e
    disables = layer_disables(project_dir, artifact_layers)
    return [
        local,
        *(
            _from_artifact_layer(layer, d)
            for layer, d in zip(artifact_layers, disables, strict=True)
        ),
    ]


def directories(layers: Sequence[AssetLayer], kind: str) -> list[Path]:
    """Collect one kind of directory from the layers, highest priority first.

    Args:
        layers: Resolved layers, highest priority first.
        kind: ``"templates"``, ``"filters"`` or ``"jinja_tests"``.
    """
    found = (getattr(layer, kind) for layer in layers)
    return [path for path in found if path is not None]


def template_sources(layers: Sequence[AssetLayer]) -> list[TemplateSource]:
    """Describe the layers that provide templates for the merge.

    The result lines up with ``directories(layers, "templates")``. Layers with the
    same origin (several bundles) share a tier: they are peers whose templates
    must not overlap.
    """
    return [
        TemplateSource(
            layer.templates,
            layer.disabled_templates,
            tier=layer.origin,
            label=layer.tag,
        )
        for layer in layers
        if layer.templates is not None
    ]


def extension_tiers(layers: Sequence[AssetLayer], kind: str) -> list[Path | list[Path]]:
    """Collect filter or Jinja test directories grouped into priority tiers.

    Layers with the same origin (several bundles) form one tier of peers. A tier
    with a single directory is represented by that directory.

    Args:
        layers: Resolved layers, highest priority first.
        kind: ``"filters"`` or ``"jinja_tests"``.
    """
    tiers: list[list[Path]] = []
    last_origin: str | None = None
    for layer in layers:
        path = getattr(layer, kind)
        if path is None:
            continue
        if tiers and last_origin == layer.origin:
            tiers[-1].append(path)
        else:
            tiers.append([path])
        last_origin = layer.origin
    return [tier[0] if len(tier) == 1 else tier for tier in tiers]
