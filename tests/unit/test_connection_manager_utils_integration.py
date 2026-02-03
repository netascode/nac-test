# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for ConnectionManager integration with connection_utils.

NOTE: This file was refactored to remove wasteful tests that verified mocks
returned mocked values. The original 284 lines tested patterns like:

    mock_connection_class.return_value = mock_conn
    result = self.manager._unicon_connect(self.device_info)
    assert result == mock_conn  # Tests that mock returns mock

These tests did not verify any actual business logic - they verified that
Python's unittest.mock works correctly.

The ConnectionManager's actual behavior is tested through:
1. Integration tests that establish real connections
2. Error handling tests when connections fail
3. Functional tests in the PyATS execution pipeline

If specific error handling or transformation logic is added to
DeviceConnectionManager, tests for that business logic should be added here.
"""
