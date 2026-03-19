# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[Production] Consolidated SD-WAN Device Verifications using Dynamic Loop Marking
----------------------------------------------------------------------------------
This consolidates multiple verification types into a SINGLE subprocess using PyATS
native aetest.loop.mark() pattern to eliminate subprocess overhead.

Performance Goal:
  - Current: 2 test files → 2 run() calls → 2 subprocesses → overhead
  - Target: 2 verification types → 1 run() call → 1 subprocess → single unified test

Pattern:
  - CommonSetup marks verification types for dynamic looping
  - DeviceVerification runs once per type, all in same subprocess
  - Each iteration loads config dynamically per verification_type parameter

Verification Types:
  1. sdwan_control - Verify All SD-WAN Control Connections Are Up
  2. sdwan_sync - Verify All SD-WAN Edge Configurations Are In-Sync
"""

import time

import jmespath
from nac_test_pyats_common.iosxe import IOSXETestBase
from pyats import aetest

from nac_test.pyats_core.reporting.types import ResultStatus

# Production Verification Configs (1 type for clean performance testing)
VERIFICATION_CONFIGS = {
    "sdwan_control": {
        "title": "Verify All SD-WAN Control Connections Are Up",
        "description": "This test validates the operational state of all SD-WAN control connections "
        "on the device. SD-WAN control connections are essential for establishing secure communication "
        "between the device and SD-WAN controllers (vSmart and vManage), enabling OMP route exchange, "
        "policy enforcement, and centralized management. Ensuring that all control connections are "
        "in the 'up' state is critical for the health and stability of the SD-WAN fabric, guaranteeing "
        "that configuration changes and routing updates are properly propagated across the network.",
        "resource_type": "SD-WAN Control Connection",
        "api_endpoint": "show sdwan control connections",
        "expected_values": {
            "state": "up",
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_connections",
            "connections_up",
            "connections_not_up",
        ],
    },
}


class CommonSetup(aetest.CommonSetup):
    """Mark testcase to loop over verification types using dynamic loop marking"""

    @aetest.subsection
    def mark_verification_loops(self):
        """
        KEY PATTERN: Use aetest.loop.mark() to run DeviceVerification
        once per verification type, all in the SAME subprocess.

        This eliminates subprocess spawns (1 types - 1 subprocess = savings).
        """
        verification_types = list(VERIFICATION_CONFIGS.keys())

        # Dynamic loop marking: DeviceVerification runs once per type
        aetest.loop.mark(DeviceVerification, verification_type=verification_types)

        print(
            f"✅ Marked DeviceVerification for dynamic looping over {len(verification_types)} verification types"
        )
        print(f"   Verification types: {verification_types}")


class DeviceVerification(IOSXETestBase):
    """
    [IOS-XE] Consolidated Device Verification (Dynamic Loop Pattern)

    Runs once per verification_type parameter, all in SAME subprocess.
    Each iteration loads config dynamically and delegates to base class.
    """

    @aetest.test
    def test_device_verification(self, verification_type: str, steps):
        """
        Entry point - loads config for this verification type and delegates to base class.

        Args:
            verification_type: Key from VERIFICATION_CONFIGS (e.g., "sdwan_control", "sdwan_sync")
            steps: PyATS steps object for structured test reporting
        """
        # Load config for this verification type
        config = VERIFICATION_CONFIGS[verification_type]

        # Set TEST_CONFIG dynamically (base class reads this)
        self.TEST_CONFIG = {
            "resource_type": config["resource_type"],
            "api_endpoint": config["api_endpoint"],
            "expected_values": config["expected_values"],
            "log_fields": config["log_fields"],
        }

        # Store verification type for use in helper methods
        self._current_verification_type = verification_type

        self.logger.info(
            f"Running verification type: {verification_type} - {config['title']}"
        )

        # Delegate to base class orchestration
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """
        Returns verification context based on current verification type.

        For production, returns single item per type. Can be extended to return
        multiple items (e.g., one per interface, one per VPN, etc.).
        """
        verification_type = self._current_verification_type

        if verification_type == "sdwan_control":
            return [
                {
                    "check_type": "sdwan_control_connection_state",
                    "verification_scope": "all_sdwan_control_connections",
                }
            ]
        elif verification_type == "sdwan_sync":
            return [
                {
                    "check_type": "sdwan_config_sync_status",
                    "verification_scope": "global_system_status",
                }
            ]
        else:
            # Fallback for unknown types
            return [
                {
                    "check_type": f"{verification_type}_check",
                    "verification_scope": "global",
                }
            ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification logic - dispatches to type-specific handler.

        Args:
            semaphore: Asyncio semaphore for concurrency control
            client: SSH connection client (not used in SSH tests)
            context: Dictionary containing check_type and verification_scope

        Returns:
            Dictionary containing verification result with status, reason, metadata
        """
        verification_type = self._current_verification_type

        # Dispatch to type-specific verification
        if verification_type == "sdwan_control":
            return await self._verify_sdwan_control_connections(
                semaphore, client, context
            )
        elif verification_type == "sdwan_sync":
            return await self._verify_sdwan_config_sync(semaphore, client, context)
        else:
            # Fallback for unknown types
            return self.format_verification_result(
                status=ResultStatus.FAILED,
                context=context,
                reason=f"Unknown verification type: {verification_type}",
                api_duration=0,
            )

    async def _verify_sdwan_control_connections(self, semaphore, client, context):
        """
        Verification: Discover ALL SD-WAN control connections and verify their state is 'up'.

        This is extracted from verify_iosxe_control.py and adapted for consolidated pattern.
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
                    error_msg = (
                        f"Failed to execute or parse command '{command}': {str(e)}"
                    )
                    self.logger.error(
                        f"Command execution/parsing exception: {error_msg}",
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
                        api_duration=api_duration,
                    )

                api_duration = command_duration + parse_duration

                context["api_context"] = api_context

                if parsed_output is None:
                    context["display_context"] = "SD-WAN Control Connections -> State"
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
                        parsed_output,
                    )
                    or []
                )

                if not all_connections:
                    context["display_context"] = "SD-WAN Control Connections -> State"
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
                    peer_system_ip = (
                        jmespath.search("peer_system_ip", conn) or "Unknown"
                    )
                    peer_private_ip = (
                        jmespath.search("peer_private_ip", conn) or "Unknown"
                    )
                    peer_public_ip = (
                        jmespath.search("peer_public_ip", conn) or "Unknown"
                    )
                    controller_group_id = (
                        jmespath.search("controller_group_id", conn) or "Unknown"
                    )

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
                    context["display_context"] = "SD-WAN Control Connections -> State"
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
                    context["display_context"] = "SD-WAN Control Connections -> State"
                    failures_text = "\n".join(failures)
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
                            f"{failures_text}\n\n"
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
                error_msg = (
                    f"Exception during SD-WAN control connection check: {str(e)}"
                )
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

    async def _verify_sdwan_config_sync(self, semaphore, client, context):
        """
        Verification: Check SD-WAN system configuration sync status.

        This is extracted from verify_sdwan_sync.py and adapted for consolidated pattern.
        """
        async with semaphore:
            try:
                command = self.TEST_CONFIG["api_endpoint"]

                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"],
                    "SD-WAN System Configuration Sync",
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
                    context["display_context"] = "SD-WAN Configuration Sync -> Status"
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

                context["api_context"] = api_context

                if parsed_output is None:
                    context["display_context"] = "SD-WAN Configuration Sync -> Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=f"Parsed output is None for command: {command}",
                        api_duration=api_duration,
                    )

                # Extract config_status from parsed output
                # Genie parser structure may vary, this is a simplified example
                config_status = jmespath.search("config_status", parsed_output)

                expected_values = self.TEST_CONFIG["expected_values"]
                expected_status = expected_values.get("config_status", "In Sync")

                context["config_sync_status"] = config_status or "Not Found"

                if config_status == expected_status:
                    context["display_context"] = "SD-WAN Configuration Sync -> Status"
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**SD-WAN Configuration Sync Check PASSED**\n\n"
                            f"Device configuration status is '{config_status}'.\n\n"
                            f"• Configuration is synchronized with SD-WAN Manager\n"
                            f"• Device is running expected configuration\n\n"
                            f"**Configuration Sync Status:**\n"
                            f"• Status: {config_status}\n"
                            f"• Expected: {expected_status}\n"
                            f"• Command execution duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    context["display_context"] = "SD-WAN Configuration Sync -> Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**SD-WAN Configuration Sync Check FAILED**\n\n"
                            f"Device configuration status is '{config_status}', expected '{expected_status}'.\n\n"
                            f"This indicates the device configuration is not synchronized with SD-WAN Manager.\n\n"
                            f"**Configuration Sync Status:**\n"
                            f"• Status: {config_status}\n"
                            f"• Expected: {expected_status}\n\n"
                            f"**Please verify:**\n"
                            f"• Device has connectivity to SD-WAN Manager\n"
                            f"• Configuration push completed successfully\n"
                            f"• Device is not in maintenance mode\n"
                            f"• No certificate or authentication issues\n"
                            f"• Command execution duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = f"Exception during SD-WAN config sync check: {str(e)}"
                self.logger.error(
                    f"Exception for SD-WAN Configuration Sync Check: {error_msg}",
                    exc_info=True,
                )
                context["display_context"] = "SD-WAN Configuration Sync -> Status"
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


class CommonCleanup(aetest.CommonCleanup):
    """Cleanup after all verifications complete"""

    @aetest.subsection
    def cleanup(self):
        print("✅ All consolidated verifications complete")
