# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Robot Framework reporting module.

This module provides parsing and report generation for Robot Framework test results,
following the same architectural pattern as PyATS reporting.
"""

from nac_test.robot.reporting.robot_generator import RobotReportGenerator
from nac_test.robot.reporting.robot_parser import RobotResultParser, TestDataCollector

__all__ = ["RobotResultParser", "TestDataCollector", "RobotReportGenerator"]
