# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Backward-compatibility shim -- moved to nac_test.robot.pabot.

.. deprecated:: 2.0
    ``nac_test.pabot`` will be removed in a future release.
    Update imports to ``nac_test.robot.pabot``.
"""

import warnings

warnings.warn(
    "nac_test.pabot has moved to nac_test.robot.pabot. "
    "Update your imports; this shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from nac_test.robot.pabot import run_pabot  # noqa: E402, F401

__all__ = ["run_pabot"]
