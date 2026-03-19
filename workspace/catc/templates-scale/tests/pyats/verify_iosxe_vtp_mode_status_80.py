# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify VTP Mode Status
------------------------------
This job file verifies that the VTP Operating Mode on an IOS-XE device is set to 'transparent' or 'off' as required for proper VLAN configuration integrity under Catalyst Center management.
"""

import time
from pyats import aetest

import jmespath
from nac_test_pyats_common.iosxe import IOSXETestBase
from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify VTP Operating Mode is Set to Transparent or Off_80"

DESCRIPTION = """This test validates the VTP (VLAN Trunking Protocol) Operating Mode on IOS-XE devices.
VTP is a protocol that manages VLAN information across network switches, and the operating mode
determines how the device participates in VTP. For Catalyst Center managed environments,
VTP should be set to 'transparent' or 'off' to ensure that VLAN configuration integrity is preserved and
to prevent unintended propagation or overwriting of VLAN data. This test ensures the device's
VTP mode aligns with best practices for intent-based management and network stability."""

SETUP = (
    "* SSH access to the target IOS-XE network device is available.\n"
    "* Authentication credentials for the device are valid and configured.\n"
    "* The device is running IOS-XE and supports the 'show vtp status' CLI command.\n"
    "* Catalyst Center management is enabled or intended for this device.\n"
)

PROCEDURE = (
    "* Establish SSH connection to the IOS-XE network device.\n"
    "* Execute the CLI command: *show vtp status*.\n"
    "* Parse the command output using the Genie parser to extract structured data.\n"
    "* Extract the `operating_mode` attribute from the parsed VTP status data.\n"
    "* Compare the discovered VTP Operating Mode against the expected value (typically 'transparent' or 'off') as specified in the jobfile parameters.\n"
    "* For EACH discovered VTP status context:\n"
    "    * Verify that the operating mode is 'transparent' or 'off'.\n"
)

PASS_FAIL_CRITERIA = (
    "**This test passes when all of the following conditions are met:**\n"
    "\n"
    "* The device supports and returns valid output for the 'show vtp status' CLI command.\n"
    "* The VTP Operating Mode is discovered and its value is either 'transparent' or 'off', matching the expected value from jobfile parameters.\n"
    "\n"
    "**This test fails if any of the following criteria are met:**\n"
    "\n"
    "* The device does not support VTP or the 'show vtp status' CLI command is unavailable.\n"
    "* No VTP status information is discovered in the command output.\n"
    "* The VTP Operating Mode is not 'transparent' or 'off', or does not match the expected value from jobfile parameters.\n"
    "* The CLI command execution fails or returns an error.\n"
    "* The Genie parser fails to parse the command output.\n"
)


class VerifyVTPOperatingMode_80(IOSXETestBase):
    """
    [IOS-XE] Verify VTP Mode Status

    Executes 'show vtp status' to verify that the VTP Operating Mode is set to the expected value
    ('transparent' or 'off'), which is required for VLAN configuration integrity under Catalyst Center management.
    """

    TEST_CONFIG = {
        "resource_type": "VTP Operating Mode",
        "api_endpoint": "show vtp status",
        "expected_values": {
            "vtp.operating_mode": "transparent",  # The expected value should be set by jobfile parameters.
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_items",
            "healthy_items",
            "unhealthy_items",
        ],
    }

    @aetest.test
    def test_vtp_operating_mode(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """
        Returns a single context to trigger the global VTP operating mode check.
        """
        return [
            {
                "check_type": "vtp_operating_mode_check",
                "verification_scope": "global_vtp_status",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification: Discover VTP operating mode and verify it matches expected value.

        Executes 'show vtp status', parses the output using Genie,
        and verifies that the VTP operating mode is set to the expected value.

        Args:
            semaphore: Asyncio semaphore for concurrency control.
            client: SSH connection client.
            context: Dictionary containing check_type and verification_scope.

        Returns:
            Dictionary containing verification result with status, reason, and metadata.
        """
        async with semaphore:
            try:
                command = self.TEST_CONFIG["api_endpoint"]

                # Build API context for command-result linking
                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"],
                    "VTP Global Status",
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
                    self.logger.error(
                        f"Command execution/parsing exception: {error_msg}",
                        exc_info=True,
                    )

                    reason = (
                        f"PyATS Framework Exception: {error_msg}\n\n"
                        f"This is a PyATS code issue, not an issue with your data model, "
                        f"Catalyst Center configuration, or your network devices.\n\n"
                        f"Please contact Cisco TAC for support with this error."
                    )

                    context["display_context"] = "VTP Operating Mode -> Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=reason,
                        api_duration=api_duration,
                    )

                api_duration = command_duration + parse_duration

                context["api_context"] = api_context

                if parsed_output is None:
                    context["display_context"] = "VTP Operating Mode -> Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=f"Parsed output is None for command: {command}",
                        api_duration=api_duration,
                    )

                # Use JMESPath to extract the VTP status dictionary as a single-item list for uniform logic
                vtp_status_list = jmespath.search("vtp", parsed_output)
                if vtp_status_list is None:
                    vtp_status_list = []
                else:
                    vtp_status_list = [vtp_status_list]

                if not vtp_status_list:
                    context["display_context"] = "VTP Operating Mode -> Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No VTP status information discovered.\n\n"
                            "This indicates that either:\n"
                            "• VTP is not supported or enabled on this device\n"
                            "• The device is not running IOS-XE or the required CLI is unavailable\n\n"
                            "Please verify:\n"
                            "• The device is running IOS-XE and supports VTP\n"
                            "• The 'show vtp status' CLI command is available\n"
                        ),
                        api_duration=api_duration,
                    )

                expected_values = self.TEST_CONFIG["expected_values"]
                attributes_to_verify = expected_values.keys()

                all_items_healthy = True
                validation_results = []
                failures = []
                healthy_count = 0
                unhealthy_count = 0

                for vtp_item in vtp_status_list:
                    item_failures = []
                    attribute_statuses = []

                    for attr_key in attributes_to_verify:
                        actual_value = jmespath.search(attr_key, {"vtp": vtp_item})
                        if actual_value is None:
                            actual_value = "Not Found"
                        elif actual_value == "":
                            actual_value = "<empty>"

                        expected_value = expected_values[attr_key]

                        # Additional check: Ensure value is 'transparent' or 'off'
                        allowed_modes = {"transparent", "off"}
                        if attr_key == "vtp.operating_mode":
                            if str(actual_value).lower() not in allowed_modes:
                                item_failures.append(
                                    f"  • {attr_key}: Must be 'transparent' or 'off', got '{actual_value}'"
                                )
                        if str(actual_value) != str(expected_value):
                            item_failures.append(
                                f"  • {attr_key}: Expected '{expected_value}', got '{actual_value}'"
                            )

                        attribute_statuses.append(f"{attr_key}={actual_value}")

                    if item_failures:
                        all_items_healthy = False
                        unhealthy_count += 1
                        failure_detail = (
                            f"**VTP Operating Mode**\n"
                            f"  Status: FAILED\n"
                            f"  Failures:\n" + "\n".join(item_failures)
                        )
                        failures.append(failure_detail)

                        validation_results.append(
                            f"❌ VTP Operating Mode - " + ", ".join(attribute_statuses)
                        )
                    else:
                        healthy_count += 1
                        validation_results.append(
                            f"✅ VTP Operating Mode - " + ", ".join(attribute_statuses)
                        )

                context["total_items"] = len(vtp_status_list)
                context["healthy_items"] = healthy_count
                context["unhealthy_items"] = unhealthy_count

                result_summary = "\n".join(validation_results)
                context["display_context"] = "VTP Operating Mode -> Status"

                if all_items_healthy:
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**VTP Operating Mode Check PASSED**\n\n"
                            f"VTP Operating Mode is set to '{expected_values['vtp.operating_mode']}' as required.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**VTP Status:**\n"
                            f"• VTP Operating Mode: {expected_values['vtp.operating_mode']}\n"
                            f"• Total items checked: {len(vtp_status_list)}\n"
                            f"• All items healthy: Yes\n"
                            f"• Command execution duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**VTP Operating Mode Check FAILED**\n\n"
                            f"One or more failures detected in VTP Operating Mode configuration.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Detailed Failures:**\n"
                            f"{chr(10).join(failures)}\n\n"
                            f"**VTP Status:**\n"
                            f"• Total items checked: {len(vtp_status_list)}\n"
                            f"• Healthy items: {healthy_count}\n"
                            f"• Unhealthy items: {unhealthy_count}\n\n"
                            f"**Please verify:**\n"
                            f"• VTP Operating Mode is set to 'transparent' or 'off' as required for Catalyst Center\n"
                            f"• VLAN configuration integrity is maintained\n"
                            f"• The device is under Catalyst Center management\n"
                            f"• No inconsistent VTP configurations are present\n"
                            f"• Command execution duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = f"Exception during VTP Operating Mode check: {str(e)}"
                self.logger.error(
                    f"Exception for VTP Operating Mode Check: {error_msg}",
                    exc_info=True,
                )
                context["display_context"] = "VTP Operating Mode -> Status"
                reason = (
                    f"PyATS Framework Exception: {error_msg}\n\n"
                    f"This is a PyATS code issue, not an issue with your data model, "
                    f"Catalyst Center configuration, or your network devices.\n\n"
                    f"Please contact Cisco TAC for support with this error."
                )
                return self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason=reason,
                    api_duration=0,
                )
