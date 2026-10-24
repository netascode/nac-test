# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Daniel Schmidt

"""Merging of template directories from several layers.

A template is identified by its path relative to its template directory. If
several layers provide the same relative path, the highest priority layer wins.
The merged tree is a real copy (not symlinks): PyATS computes test names
relative to the template directory and breaks on symlinked files.
"""

import logging
import os
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from nac_artifacts import DisableEntry, DisableMatcher

from nac_test.core.constants import MERGED_TEMPLATES_DIRNAME
from nac_test.exceptions import TemplateError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TemplateSource:
    """A template directory taking part in a merge.

    Attributes:
        path: The template directory.
        disabled: Entries (relative paths or globs) that disable templates of this
            directory; matching files are dropped before the merge.
        tier: Sources of the same non-empty tier are peers: they must not provide
            the same relative path. Other sources are ordered by priority.
        label: Name for messages (defaults to the path).
    """

    path: Path
    disabled: tuple[DisableEntry, ...] = ()
    tier: str = ""
    label: str = ""

    @property
    def tag(self) -> str:
        """Name used in messages."""
        return self.label or str(self.path)


def _as_sources(sources: Sequence[Path | TemplateSource]) -> list[TemplateSource]:
    return [
        s if isinstance(s, TemplateSource) else TemplateSource(Path(s)) for s in sources
    ]


def _tiers(sources: Sequence[TemplateSource]) -> list[list[TemplateSource]]:
    """Group consecutive sources with the same tier; untiered sources stand alone."""
    tiers: list[list[TemplateSource]] = []
    for source in sources:
        if tiers and source.tier and tiers[-1][0].tier == source.tier:
            tiers[-1].append(source)
        else:
            tiers.append([source])
    return tiers


@dataclass(frozen=True)
class TemplatePlan:
    """Outcome of resolving which source provides each template.

    Attributes:
        files: Winning file for every relative path (POSIX style).
        origins: Source directory each relative path was taken from.
        shadowed: ``(relative path, shadowed directory, winning directory)`` for
            every file that a higher priority source replaced.
        disabled: ``(relative path, source directory, entry)`` for every file an
            ``overrides.yaml`` entry removed.
        unmatched: Entries that matched no template in any source.
    """

    files: dict[str, Path] = field(default_factory=dict)
    origins: dict[str, Path] = field(default_factory=dict)
    shadowed: list[tuple[str, Path, Path]] = field(default_factory=list)
    disabled: list[tuple[str, Path, DisableEntry]] = field(default_factory=list)
    unmatched: list[DisableEntry] = field(default_factory=list)


@dataclass(frozen=True)
class MergedTemplates:
    """Result of merging template directories.

    Attributes:
        root: Directory holding the merged tree.
        origins: Source directory each relative path (POSIX style) was taken from.
        shadowed: ``(relative path, shadowed directory, winning directory)`` for
            every file that a higher priority layer replaced.
        disabled: ``(relative path, source directory, entry)`` for every file an
            ``overrides.yaml`` entry removed.
    """

    root: Path
    origins: dict[str, Path] = field(default_factory=dict)
    shadowed: list[tuple[str, Path, Path]] = field(default_factory=list)
    disabled: list[tuple[str, Path, DisableEntry]] = field(default_factory=list)


def _is_inside(path: Path, parent: Path) -> bool:
    """Whether ``path`` is ``parent`` or below it."""
    return path == parent or parent in path.parents


def _collect_files(source: Path, skip: Sequence[Path]) -> dict[str, Path]:
    """Map relative POSIX paths to files below ``source``, ignoring ``skip`` trees."""
    files: dict[str, Path] = {}
    # A skipped path that contains the source itself (e.g. an output directory above
    # the template directory) must not hide the source
    inside = [s for s in skip if s != source and _is_inside(s, source)]
    for dirpath, dirnames, filenames in os.walk(source):
        current = Path(dirpath).absolute()
        dirnames[:] = [
            d for d in dirnames if not any(_is_inside(current / d, s) for s in inside)
        ]
        for filename in filenames:
            path = Path(dirpath, filename)
            files[path.relative_to(source).as_posix()] = path
    return files


def plan_template_merge(
    sources: Sequence[Path | TemplateSource],
    exclude: Sequence[Path] = (),
) -> TemplatePlan:
    """Work out which file wins for every relative path, without copying anything.

    Args:
        sources: Template directories (plain paths or :class:`TemplateSource`),
            highest priority first. Entries disabling templates are dropped from
            their source before sources are combined, so a higher source can still
            provide the same path.
        exclude: Directories to leave out, such as Jinja filters kept inside a
            template directory (PyATS discovery must not see them either).

    Raises:
        TemplateError: If two peer sources (same tier) provide the same path.
    """
    resolved = [
        TemplateSource(Path(src.path).absolute(), src.disabled, src.tier, src.label)
        for src in _as_sources(sources)
    ]
    skip = [Path(e).absolute() for e in exclude]
    files: dict[str, Path] = {}
    origins: dict[str, Path] = {}
    shadowed: list[tuple[str, Path, Path]] = []
    removed: list[tuple[str, Path, DisableEntry]] = []
    all_entries: dict[DisableEntry, None] = {}
    # Lowest priority tier first, so later (higher priority) tiers replace earlier ones
    for tier in reversed(_tiers(resolved)):
        tier_files: dict[str, tuple[Path, TemplateSource]] = {}
        for source in tier:
            matcher = DisableMatcher(source.disabled, glob=True)
            all_entries.update(dict.fromkeys(source.disabled))
            for rel, path in _collect_files(source.path, skip).items():
                entry = matcher.match(rel)
                if entry is not None:
                    removed.append((rel, source.path, entry))
                    continue
                if rel in tier_files:
                    raise TemplateError(
                        f"Template '{rel}' is provided by both "
                        f"{tier_files[rel][1].tag} and {source.tag}"
                    )
                tier_files[rel] = (path, source)
        for rel, (path, source) in tier_files.items():
            if rel in files:
                shadowed.append((rel, origins[rel], source.path))
            files[rel] = path
            origins[rel] = source.path
    used = {entry for _, _, entry in removed}
    return TemplatePlan(
        files=files,
        origins=origins,
        shadowed=shadowed,
        disabled=removed,
        unmatched=[e for e in all_entries if e not in used],
    )


def merge_template_dirs(
    sources: Sequence[Path | TemplateSource],
    target: Path,
    exclude: Sequence[Path] = (),
) -> MergedTemplates:
    """Merge template directories into ``target``, highest priority source first.

    Args:
        sources: Template directories (plain paths or :class:`TemplateSource`),
            highest priority first.
        target: Directory to (re)create with the merged tree.
        exclude: Directories to leave out of the merged tree.

    Raises:
        ValueError: If ``target`` is a source directory or contains one, since
            it is deleted before the merge.
        TemplateError: If two peer sources provide the same path.
    """
    absolute_sources = [Path(src.path).absolute() for src in _as_sources(sources)]
    target = Path(target).absolute()
    for source in absolute_sources:
        if _is_inside(source, target):
            raise ValueError(
                f"Merge target {target} must not be or contain the template "
                f"directory {source}"
            )
    plan = plan_template_merge(sources, [target, *exclude])

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for rel, path in plan.files.items():
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    logger.info(
        "Merged %d template files from %d directories into %s",
        len(plan.files),
        len(absolute_sources),
        target,
    )
    return MergedTemplates(
        root=target,
        origins=plan.origins,
        shadowed=plan.shadowed,
        disabled=plan.disabled,
    )


def effective_templates_dir(
    sources: Sequence[Path | TemplateSource],
    output_dir: Path,
    exclude: Sequence[Path] = (),
) -> Path | None:
    """Return the directory nac-test should read templates from.

    Args:
        sources: Template directories (plain paths or :class:`TemplateSource`),
            highest priority first.
        output_dir: Output directory; a merged tree goes into a subdirectory.
        exclude: Directories to leave out of a merged tree.

    Returns:
        None without sources. The source itself if there is only one and nothing
        in it is disabled (no copy, nothing changes for a single template
        directory). Otherwise a merged copy in a subdirectory of ``output_dir``.

    Raises:
        TemplateError: If two peer sources provide the same path.
    """
    if not sources:
        return None
    if len(sources) == 1 and not plan_template_merge(sources, exclude).disabled:
        return Path(_as_sources(sources)[0].path)
    return merge_template_dirs(
        sources, Path(output_dir) / MERGED_TEMPLATES_DIRNAME, exclude
    ).root
