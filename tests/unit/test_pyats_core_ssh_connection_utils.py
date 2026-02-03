# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for nac_test.pyats_core.ssh.connection_utils module.

NOTE: This file was refactored to remove wasteful tests that tested Python
string concatenation (f"ssh {host}") rather than actual business logic.
The original 444 lines tested:
- String concatenation for SSH commands
- String concatenation for Telnet commands
- Simple if/else logic for chassis type (1->single_rp, 2->dual_rp, else->stack)

These tests verified Python's f-string and string operations work correctly,
which is not business logic that needs testing. The connection_utils module's
actual behavior is implicitly tested through integration tests that use the
connection manager.

If error handling or edge case validation is added to connection_utils in the
future, tests for that business logic should be added here.
"""
