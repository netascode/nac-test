# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Backward-compatibility shim -- this import path is deprecated.

.. deprecated:: 2.0
    ``nac_test.pabot`` is deprecated and will be removed in a future release.
    A stable replacement API is under development.
"""

import warnings
from pathlib import Path
from typing import Any

warnings.warn(
    "'nac_test.pabot' is deprecated and will be removed in a future release. "
    "The replacement public API is being finalized; "
    "monitor the nac-test changelog for migration guidance.",
    DeprecationWarning,
    stacklevel=2,
)

from nac_test.robot.pabot import run_pabot as _canonical_run_pabot  # noqa: E402


def run_pabot(path: str | Path, **kwargs: Any) -> int:
    """Backward-compatible wrapper for run_pabot with str→Path coercion.

    Args:
        path: Robot output directory (str or Path).
        **kwargs: Forwarded to canonical run_pabot.

    Returns:
        int: Pabot exit code.
    """
    if isinstance(path, str):
        path = Path(path)
    return _canonical_run_pabot(path, **kwargs)


__all__ = ["run_pabot"]
