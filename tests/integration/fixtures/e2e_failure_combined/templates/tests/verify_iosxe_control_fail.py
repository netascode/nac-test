# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify SD-WAN Tunnel Statistics (FAILURE TEST)
-------------------------------------------------------
This test is designed to fail for integration testing purposes.
It uses a command that is not in the mock data, causing validation to fail.
"""

import time
from pyats import aetest

import jmespath
from nac_test_pyats_common.iosxe import IOSXETestBase
from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify SD-WAN Tunnel Statistics (Failure Test)"

DESCRIPTION = """This test is designed to fail for integration testing. 
It queries a command that returns no data, causing validation failures."""

SETUP = "* This is a test designed to fail.\n"

PROCEDURE = (
    "* Execute command that is not in mock data.\n"
    "* Validation fails due to missing data.\n"
)

PASS_FAIL_CRITERIA = "**This test is designed to fail.**\n"


class VerifySdwanTunnelStatistics(IOSXETestBase):
    """
    [IOS-XE] Test designed to fail - uses non-existent command
    """

    TEST_CONFIG = {
        "resource_type": "SD-WAN Tunnel Statistics",
        "api_endpoint": "show sdwan tunnel statistics bfd",  # NOT in mock data
        "expected_values": {
            "state": "up",
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_tunnels",
        ],
    }

    @aetest.test
    def test_sdwan_tunnel_statistics(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """Returns a single context to trigger check."""
        return [
            {
                "check_type": "sdwan_tunnel_statistics",
                "verification_scope": "all_tunnels",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification: Execute command and parse (will fail due to no data).
        """
        async with semaphore:
            try:
                command = self.TEST_CONFIG["api_endpoint"]

                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"],
                    "All Tunnels",
                    check_type=context.get("check_type"),
                    verification_scope=context.get("verification_scope"),
                )

                start_time = time.time()

                try:
                    with self.test_context(api_context):
                        output = await self.execute_command(command)
                    command_duration = time.time() - start_time

                    parse_start = time.time()
                    parsed_output = self.parse_output(command, output=output)
                    parse_duration = time.time() - parse_start

                except Exception as e:
                    api_duration = time.time() - start_time
                    error_msg = (
                        f"Failed to execute or parse command '{command}': {str(e)}"
                    )
                    context["display_context"] = "SD-WAN Tunnel Statistics"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=error_msg,
                        api_duration=api_duration,
                    )

                api_duration = command_duration + parse_duration
                context["api_context"] = api_context

                # Check if parsed output is empty or None
                if parsed_output is None or not parsed_output:
                    context["display_context"] = "SD-WAN Tunnel Statistics"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No tunnel statistics discovered.\n\n"
                            "This test is designed to fail for integration testing."
                        ),
                        api_duration=api_duration,
                    )

                # If we somehow got data, fail anyway (shouldn't happen)
                context["display_context"] = "SD-WAN Tunnel Statistics"
                return self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason="Test designed to fail (unexpected data received)",
                    api_duration=api_duration,
                )

            except Exception as e:
                error_msg = f"Exception during tunnel statistics check: {str(e)}"
                context["display_context"] = "SD-WAN Tunnel Statistics"
                return self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason=error_msg,
                    api_duration=0,
                )
