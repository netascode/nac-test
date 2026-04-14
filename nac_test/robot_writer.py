# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Backward-compatibility shim -- this import path is deprecated.

.. deprecated:: 2.0
    ``nac_test.robot_writer`` is deprecated and will be removed in a future release.
    A stable replacement API is under development.
"""

import warnings
from pathlib import Path
from typing import Any

warnings.warn(
    "'nac_test.robot_writer' is deprecated and will be removed in a future release. "
    "The replacement public API is being finalized; "
    "monitor the nac-test changelog for migration guidance.",
    DeprecationWarning,
    stacklevel=2,
)

from nac_test.robot.robot_writer import (  # noqa: E402
    RobotWriter as _CanonicalRobotWriter,
)


def _coerce_optional_path(value: str | Path | None) -> Path | None:
    """Coerce a legacy string path to ``Path``, treating empty string as ``None``."""
    if value is None or value == "":
        return None
    return Path(value) if isinstance(value, str) else value


class RobotWriter(_CanonicalRobotWriter):
    """Backward-compatible RobotWriter subclass with str→Path coercion."""

    def __init__(
        self,
        data_paths: list[str | Path],
        filters_path: str | Path | None,
        tests_path: str | Path | None,
        **kwargs: Any,
    ) -> None:
        """Initialize RobotWriter with automatic str→Path coercion.

        Args:
            data_paths: List of data file paths (str or Path).
            filters_path: Filters directory path (str, Path, or None; empty str treated as None).
            tests_path: Tests directory path (str, Path, or None; empty str treated as None).
            **kwargs: Additional arguments forwarded to canonical RobotWriter.
        """
        super().__init__(
            [Path(p) if isinstance(p, str) else p for p in data_paths],
            _coerce_optional_path(filters_path),
            _coerce_optional_path(tests_path),
            **kwargs,
        )


__all__ = ["RobotWriter"]
