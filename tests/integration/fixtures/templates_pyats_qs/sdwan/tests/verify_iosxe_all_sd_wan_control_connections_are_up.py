# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify All SD-WAN Control Connections Are Up
---------------------------------------------------
This job file verifies that all SD-WAN control connections to vSmart and vManage controllers
are in the 'up' state, ensuring proper control plane operation and connectivity.
"""

import time
from pyats import aetest

import jmespath
from nac_test_pyats_common.iosxe import IOSXETestBase
from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify All SD-WAN Control Connections Are Up"

DESCRIPTION = """This test validates the operational state of all SD-WAN control connections
on the device. SD-WAN control connections are essential for establishing secure communication
between the device and SD-WAN controllers (vSmart and vManage), enabling OMP route exchange,
policy enforcement, and centralized management. Ensuring that all control connections are
in the 'up' state is critical for the health and stability of the SD-WAN fabric, guaranteeing
that configuration changes and routing updates are properly propagated across the network."""

SETUP = (
    "* SSH access to the target network device is available.\n"
    "* Authentication credentials for the device are valid and configured.\n"
    "* SD-WAN is deployed and correctly configured on the device.\n"
    "* The device is expected to have active control connections to vSmart and vManage controllers.\n"
)

PROCEDURE = (
    "* Establish SSH connection to the network device.\n"
    "* Execute the CLI command: *show sdwan control connections*.\n"
    "* Parse the command output using the Genie 'show_sdwan_control_connections' parser to obtain structured data.\n"
    "* For EACH discovered SD-WAN control connection:\n"
    "    * Extract connection attributes such as `peer_type`, `peer_system_ip`, and `state`.\n"
    "    * Verify that the `state` attribute equals `up` for every control connection.\n"
)

PASS_FAIL_CRITERIA = (
    "**This test passes when all of the following conditions are met:**\n"
    "\n"
    "* At least one SD-WAN control connection is discovered in the command output.\n"
    "* ALL discovered SD-WAN control connections have `state` equal to `up`.\n"
    "\n"
    "**This test fails if any of the following criteria are met:**\n"
    "\n"
    "* No SD-WAN control connections are discovered via CLI command.\n"
    "* ANY discovered SD-WAN control connection has `state` not equal to `up` (e.g., 'connect', 'challenge', etc.).\n"
    "* The CLI command execution fails or returns an error.\n"
    "* The Genie parser fails to parse the command output.\n"
)



class VerifySdwanControlConnectionsState(IOSXETestBase):
    """
    [IOS-XE] Verify All SD-WAN Control Connections Are Up

    Executes 'show sdwan control connections' to verify SD-WAN control plane connectivity to vSmart and vManage controllers.
    For each discovered connection, verifies the 'state' attribute is 'up'.
    """

    TEST_CONFIG = {
        "resource_type": "SD-WAN Control Connection",
        "api_endpoint": "show sdwan control connections",
        "expected_values": {
            "state": "up",  # MUST match Genie output attribute name and value
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_connections",
            "connections_up",
            "connections_not_up",
        ],
    }

    @aetest.test
    def test_sdwan_control_connections_state(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """
        Returns a single context to trigger global SD-WAN control connection state check.
        """
        return [
            {
                "check_type": "sdwan_control_connection_state",
                "verification_scope": "all_sdwan_control_connections",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification: Discover ALL SD-WAN control connections and verify their state is 'up'.

        Executes 'show sdwan control connections', parses the output using Genie,
        and verifies that all discovered connections have state='up'.

        Args:
            semaphore: Asyncio semaphore for concurrency control.
            client: SSH connection client (not used in SSH tests, but required by signature).
            context: Dictionary containing check_type and verification_scope.

        Returns:
            Dictionary containing verification result with status, reason, and metadata.
        """
        async with semaphore:
            try:
                command = self.TEST_CONFIG["api_endpoint"]

                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"],
                    "All SD-WAN Control Connections",
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
                    error_msg = f"Failed to execute or parse command '{command}': {str(e)}"
                    self.logger.error(f"Command execution/parsing exception: {error_msg}", exc_info=True)
                    context["display_context"] = "SD-WAN Control Connections -> State"
                    reason = (
                        f"PyATS Framework Exception: {error_msg}\n\n"
                        f"This is a PyATS code issue, not an issue with your data model, "
                        f"SD-WAN configuration, or your network devices.\n\n"
                        f"Please contact Cisco TAC for support with this error."
                    )
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=reason,
                        api_duration=api_duration,
                    )

                api_duration = command_duration + parse_duration

                context['api_context'] = api_context

                if parsed_output is None:
                    context['display_context'] = "SD-WAN Control Connections -> State"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=f"Parsed output is None for command: {command}",
                        api_duration=api_duration,
                    )

                # JMESPath: Get all connection objects under all local_color.*.peer_system_ip.* as a flat list
                all_connections = (
                    jmespath.search(
                        "values(local_color)[].values(peer_system_ip)[] | []",
                        parsed_output
                    ) or []
                )

                if not all_connections:
                    context['display_context'] = "SD-WAN Control Connections -> State"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No SD-WAN control connections discovered.\n\n"
                            "This indicates that either:\n"
                            "• vSmart/vManage controllers are not reachable\n"
                            "• Control connections have not yet formed\n"
                            "• SD-WAN is not configured on this device\n\n"
                            "Please verify:\n"
                            "• SD-WAN configuration and feature templates are correct\n"
                            "• Device has network connectivity to vSmart/vManage controllers\n"
                            "• There are no certificate or organization mismatches\n"
                            "• Control plane ACLs are not blocking connections\n"
                        ),
                        api_duration=api_duration,
                    )

                expected_values = self.TEST_CONFIG["expected_values"]
                attributes_to_verify = expected_values.keys()

                all_up = True
                validation_results = []
                failures = []
                up_count = 0
                not_up_count = 0

                for conn in all_connections:
                    # Identify connection by peer_type, peer_system_ip, local_color, peer_private_ip
                    peer_type = jmespath.search("peer_type", conn) or "Unknown"
                    peer_system_ip = jmespath.search("peer_system_ip", conn) or "Unknown"
                    # local_color is not in the connection object itself, so may be unknown here
                    peer_private_ip = jmespath.search("peer_private_ip", conn) or "Unknown"
                    peer_public_ip = jmespath.search("peer_public_ip", conn) or "Unknown"
                    controller_group_id = jmespath.search("controller_group_id", conn) or "Unknown"
                    state = jmespath.search("state", conn) or "Not Found"

                    item_failures = []

                    for attr_key in attributes_to_verify:
                        actual_value = jmespath.search(attr_key, conn) or "Not Found"
                        expected_value = expected_values[attr_key]
                        if str(actual_value) != str(expected_value):
                            item_failures.append(
                                f"  • {attr_key}: Expected '{expected_value}', got '{actual_value}'"
                            )

                    if item_failures:
                        all_up = False
                        not_up_count += 1
                        failure_detail = (
                            f"**SD-WAN Control Connection to {peer_type} {peer_system_ip} "
                            f"(Group: {controller_group_id}, Private IP: {peer_private_ip}, Public IP: {peer_public_ip})**\n"
                            f"  Status: FAILED\n"
                            f"  Failures:\n" + "\n".join(item_failures)
                        )
                        failures.append(failure_detail)
                        conn_status_values = [
                            f"{attr}={jmespath.search(attr, conn) or 'Not Found'}"
                            for attr in attributes_to_verify
                        ]
                        validation_results.append(
                            f"[FAIL] {peer_type} {peer_system_ip} (Group: {controller_group_id}) - "
                            + ", ".join(conn_status_values)
                        )
                    else:
                        up_count += 1
                        conn_status_values = [
                            f"{attr}={jmespath.search(attr, conn) or 'Not Found'}"
                            for attr in attributes_to_verify
                        ]
                        validation_results.append(
                            f"[PASS] {peer_type} {peer_system_ip} (Group: {controller_group_id}) - "
                            + ", ".join(conn_status_values)
                        )

                # Update context with metrics
                context["total_connections"] = len(all_connections)
                context["connections_up"] = up_count
                context["connections_not_up"] = not_up_count

                result_summary = "\n".join(validation_results)

                if all_up:
                    context['display_context'] = "SD-WAN Control Connections -> State"
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**SD-WAN Control Connection Check PASSED**\n\n"
                            f"All {len(all_connections)} discovered SD-WAN control connections are in 'up' state.\n\n"
                            f"• Ensures full SD-WAN control plane connectivity to all controllers (vSmart/vManage)\n"
                            f"• OMP routes, policies, and management are fully operational\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**SD-WAN Control Connection Status:**\n"
                            f"• Total control connections: {len(all_connections)}\n"
                            f"• Connections in 'up' state: {up_count}\n"
                            f"• All control connections up: Yes\n"
                            f"• Command execution duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    context['display_context'] = "SD-WAN Control Connections -> State"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**SD-WAN Control Connection Check FAILED**\n\n"
                            f"One or more SD-WAN control connections are not in 'up' state.\n"
                            f"This can cause OMP route distribution, policy enforcement, and centralized management to fail.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Detailed Failures:**\n"
                            f"{'\n'.join(failures)}\n\n"
                            f"**SD-WAN Control Connection Status:**\n"
                            f"• Total control connections: {len(all_connections)}\n"
                            f"• Connections in 'up' state: {up_count}\n"
                            f"• Connections not 'up': {not_up_count}\n\n"
                            f"**Please verify:**\n"
                            f"• Device has network reachability to all vSmart and vManage controllers\n"
                            f"• Control connection certificates and organization names match\n"
                            f"• There are no firewall or ACLs blocking required ports (DTLS/TLS)\n"
                            f"• Controller IP addresses, ports, and local color configurations are correct\n"
                            f"• SD-WAN feature templates are correctly applied\n"
                            f"• Device is not overloaded or out of resources\n"
                            f"• If in maintenance, expected state is documented\n"
                            f"• Command execution duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = f"Exception during SD-WAN control connection check: {str(e)}"
                self.logger.error(
                    f"Exception for SD-WAN Control Connection Check: {error_msg}",
                    exc_info=True,
                )
                context["display_context"] = "SD-WAN Control Connections -> State"
                reason = (
                    f"PyATS Framework Exception: {error_msg}\n\n"
                    f"This is a PyATS code issue, not an issue with your data model, "
                    f"SD-WAN configuration, or your network devices.\n\n"
                    f"Please contact Cisco TAC for support with this error."
                )
                return self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason=reason,
                    api_duration=0,
                )