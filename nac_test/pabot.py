# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Backward-compatibility shim -- this import path is deprecated.

.. deprecated:: 2.0
    ``nac_test.pabot`` is deprecated and will be removed in a future release.
    A stable replacement API is under development.
"""

import warnings

warnings.warn(
    "'nac_test.pabot' is deprecated and will be removed in a future release. "
    "The replacement public API is being finalized; "
    "monitor the nac-test changelog for migration guidance.",
    DeprecationWarning,
    stacklevel=2,
)

from nac_test.robot.pabot import run_pabot  # noqa: E402, F401

__all__ = ["run_pabot"]
