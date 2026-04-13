# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Backward-compatibility shim -- moved to nac_test.robot.robot_writer.

.. deprecated:: 2.0
    ``nac_test.robot_writer`` will be removed in a future release.
    Update imports to ``nac_test.robot.robot_writer``.
"""

import warnings

warnings.warn(
    "nac_test.robot_writer has moved to nac_test.robot.robot_writer. "
    "Update your imports; this shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from nac_test.robot.robot_writer import RobotWriter  # noqa: E402, F401

__all__ = ["RobotWriter"]
