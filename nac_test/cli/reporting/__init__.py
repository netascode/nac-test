# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""CLI reporting utilities for nac-test.

This package contains reporting functions for the CLI layer, including
pre-flight validation failure reports that are generated before any
test execution begins.
"""

from nac_test.cli.reporting.auth_failure import generate_auth_failure_report

__all__ = ["generate_auth_failure_report"]
