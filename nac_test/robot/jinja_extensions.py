# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Daniel Schmidt

"""Loading of Jinja filters and Jinja tests from one or several directories.

Both are Python files defining a class (``Filter`` or ``Test``) with a ``name``.
An extension is identified by that declared name, not by its file name. If
several directories define the same name, the highest priority directory wins;
two files in the same directory defining the same name are an error.

:func:`load_jinja_extensions` imports the files. :func:`declared_jinja_extensions`
resolves the same names without running any code, by reading the literal
``name`` assignment from the source; it is used for read-only inspection such
as ``--list-artifacts``.
"""

import ast
import hashlib
import importlib.machinery
import importlib.util
import logging
import os
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nac_test.exceptions import TemplateError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedExtension:
    """A loaded filter or Jinja test.

    Attributes:
        cls: The ``Filter`` or ``Test`` class, or ``None`` if the file was only
            read statically (see :func:`declared_jinja_extensions`).
        origin: Directory it was loaded from.
    """

    cls: Any
    origin: Path


UNRESOLVED_NAME = "unknown (not statically resolvable)"


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


def _resolve(
    directories: DirectorySpec,
    class_name: str,
    read: Callable[[Path], tuple[str | None, Any]],
) -> dict[str, LoadedExtension]:
    """Resolve extension names across tiers, highest priority first.

    Args:
        directories: See :func:`load_jinja_extensions`.
        class_name: ``Filter`` or ``Test``, used in messages.
        read: Returns the declared name of a file (``None`` if it cannot be
            determined) and the class (or ``None``).
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
                name, cls = read(Path(directory, filename))
                if name is None:
                    # Keyed by file so it is listed, but takes part in no
                    # duplicate or replacement check
                    in_tier[f"{filename}: {UNRESOLVED_NAME}"] = LoadedExtension(
                        cls, directory
                    )
                    continue
                if name in names_here:
                    raise TemplateError(
                        f"Duplicate {class_name.lower()} name '{name}' in "
                        f"{directory}: defined in {names_here[name]} and {filename}"
                    )
                if name in in_tier:
                    raise TemplateError(
                        f"{class_name} '{name}' is provided by both "
                        f"{in_tier[name].origin} and {directory}"
                    )
                names_here[name] = filename
                in_tier[name] = LoadedExtension(cls, directory)
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


def load_jinja_extensions(
    directories: DirectorySpec,
    *,
    class_name: str,
    module_name: str,
) -> dict[str, LoadedExtension]:
    """Load filters or Jinja tests, highest priority first.

    This imports (executes) every file. Use :func:`declared_jinja_extensions`
    to only inspect them.

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

    def read(file_path: Path) -> tuple[str | None, Any]:
        name = _module_name(module_name, file_path)
        spec = importlib.util.spec_from_file_location(
            name, file_path, loader=_NoBytecodeLoader(name, str(file_path))
        )
        assert spec is not None and spec.loader is not None  # explicit loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        cls = getattr(mod, class_name)
        return cls.name, cls

    return _resolve(directories, class_name, read)


def _declared_name(file_path: Path, class_name: str) -> str | None:
    """Read the literal ``name`` of the top-level ``class_name`` class.

    Returns:
        The name, or ``None`` if there is no such class or ``name`` is not a
        string literal assigned in its body.

    Raises:
        TemplateError: If the file is not valid Python.
    """
    try:
        tree = ast.parse(file_path.read_bytes(), filename=str(file_path))
    except (SyntaxError, ValueError) as e:
        raise TemplateError(f"Cannot parse {file_path}: {e}") from None
    name: str | None = None
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name == class_name):
            continue
        name = None  # a later definition of the class replaces an earlier one
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                targets, value = stmt.targets, stmt.value
            elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                targets, value = [stmt.target], stmt.value
            else:
                continue
            if any(isinstance(t, ast.Name) and t.id == "name" for t in targets):
                literal = isinstance(value, ast.Constant) and isinstance(
                    value.value, str
                )
                name = value.value if literal else None  # type: ignore[union-attr]
    return name


def declared_jinja_extensions(
    directories: DirectorySpec,
    *,
    class_name: str,
) -> dict[str, LoadedExtension]:
    """Resolve filters or Jinja tests like :func:`load_jinja_extensions`, without
    running them.

    Each file is parsed, not imported, and the name is read from the literal
    ``name`` assignment of its ``class_name`` class. Files whose name cannot be
    determined this way are keyed ``"<file>: unknown (not statically
    resolvable)"`` and take part in no duplicate check. The returned
    extensions have ``cls`` set to ``None``.

    Raises:
        TemplateError: If a file is not valid Python, or on duplicate names as
            in :func:`load_jinja_extensions`.
    """
    return _resolve(
        directories,
        class_name,
        lambda file_path: (_declared_name(file_path, class_name), None),
    )
