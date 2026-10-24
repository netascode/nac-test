# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Daniel Schmidt

"""Loading of Jinja filters and Jinja tests from one or several directories.

Both are Python files defining a class (``Filter`` or ``Test``) with a ``name``.
An extension is identified by that declared name, not by its file name. If
several directories define the same name, the highest priority directory wins;
two files in the same directory defining the same name are an error.
"""

import hashlib
import importlib.machinery
import importlib.util
import logging
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nac_test.exceptions import TemplateError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedExtension:
    """A loaded filter or Jinja test.

    Attributes:
        cls: The ``Filter`` or ``Test`` class.
        origin: Directory it was loaded from.
    """

    cls: Any
    origin: Path


DirectorySpec = Path | str | Sequence[Path | str | Sequence[Path]] | None


class _NoBytecodeLoader(importlib.machinery.SourceFileLoader):
    """Source loader that never writes ``__pycache__`` next to the file.

    Extensions may come from an installed module or a bundle, whose directories
    are not the user's to write to. Unlike ``sys.dont_write_bytecode`` it affects
    no other imports.
    """

    def set_data(self, path: str, data: Any, *, _mode: int = 0o666) -> None:
        """Skip writing the bytecode cache file."""


def _module_name(prefix: str, file_path: Path) -> str:
    """Return a module name that is unique for each extension file.

    Files of different directories (layers) often share a file name; the hash of
    the full path keeps them apart in ``sys.modules``.
    """
    stem = re.sub(r"\W", "_", file_path.stem)
    digest = hashlib.sha256(str(file_path.resolve()).encode()).hexdigest()[:8]
    return f"{prefix}.{stem}_{digest}"


def as_tiers(value: DirectorySpec) -> list[list[Path]]:
    """Normalize directories to priority tiers, highest priority first.

    A tier is a list of peer directories; directories of one tier must not
    define the same name. A plain path, or a sequence of paths, gives one tier
    per path; a nested sequence inside it is a tier of peers (e.g. the
    directories of several bundles).
    """
    if value is None:
        return []
    if isinstance(value, str | os.PathLike):
        return [[Path(value)]] if str(value) else []
    tiers: list[list[Path]] = []
    for item in value:
        if isinstance(item, str | os.PathLike):
            tiers.append([Path(item)])
        else:
            tiers.append([Path(p) for p in item])
    return [tier for tier in tiers if tier]


def as_directories(value: DirectorySpec) -> list[Path]:
    """Flatten a single directory, several directories or tiers to one list."""
    return [path for tier in as_tiers(value) for path in tier]


def load_jinja_extensions(
    directories: DirectorySpec,
    *,
    class_name: str,
    module_name: str,
) -> dict[str, LoadedExtension]:
    """Load filters or Jinja tests, highest priority first.

    Args:
        directories: Directories with ``.py`` files, highest priority first. See
            :func:`as_tiers` for peer directories.
        class_name: Class every file defines (``Filter`` or ``Test``).
        module_name: Prefix of the module names the files are loaded under; each
            file gets its own module below it.

    Returns:
        Loaded extensions by declared name.

    Raises:
        TemplateError: If two files in one directory, or in two peer directories,
            declare the same name.
    """
    loaded: dict[str, LoadedExtension] = {}
    # Lowest priority tier first, so later (higher priority) tiers replace earlier ones
    for tier in reversed(as_tiers(directories)):
        in_tier: dict[str, LoadedExtension] = {}
        for directory in tier:
            names_here: dict[str, str] = {}
            for filename in sorted(os.listdir(directory)):
                if Path(filename).suffix != ".py":
                    continue
                file_path = Path(directory, filename)
                name = _module_name(module_name, file_path)
                spec = importlib.util.spec_from_file_location(
                    name, file_path, loader=_NoBytecodeLoader(name, str(file_path))
                )
                if spec is None or spec.loader is None:
                    continue
                mod = importlib.util.module_from_spec(spec)
                sys.modules[name] = mod
                spec.loader.exec_module(mod)
                cls = getattr(mod, class_name)
                if cls.name in names_here:
                    raise TemplateError(
                        f"Duplicate {class_name.lower()} name '{cls.name}' in "
                        f"{directory}: defined in {names_here[cls.name]} and {filename}"
                    )
                if cls.name in in_tier:
                    raise TemplateError(
                        f"{class_name} '{cls.name}' is provided by both "
                        f"{in_tier[cls.name].origin} and {directory}"
                    )
                names_here[cls.name] = filename
                in_tier[cls.name] = LoadedExtension(cls, directory)
        for name, extension in in_tier.items():
            if name in loaded:
                logger.info(
                    "%s '%s' from %s replaces the one from %s",
                    class_name,
                    name,
                    extension.origin,
                    loaded[name].origin,
                )
            loaded[name] = extension
    return loaded
