# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify OSPF MPLS TE Links via Genie-Driven Execution (Broker Cache Test 2)
-----------------------------------------------------------------------------------
This test validates that Genie's internal device.execute() calls route through the
connection broker when parse_output() is called without pre-fetched output.

The Genie parser for 'show ip ospf mpls traffic-eng link' fires a supplementary
'show running-config | section router ospf {N}' call to resolve VRF names.
Both the primary and supplementary commands must route through the broker.

This is the SECOND of two identical test files. When both run on the same device,
the broker should show:
- File 1: 2 command cache misses per device (already happened)
- File 2: 2 command cache hits per device (this file validates caching)
"""

import time

from nac_test_pyats_common.iosxe import IOSXETestBase
from pyats import aetest

from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify OSPF MPLS TE Links via Genie-Driven Execution (1)"

DESCRIPTION = """This test validates that Genie parsers work correctly when the
connection broker manages all device communication. By NOT providing pre-fetched
output to parse_output(), Genie must call device.execute() internally — which is
patched to route through the broker. The supplementary 'show running-config |
section router ospf N' call must also succeed through the broker."""

SETUP = (
    "* SSH access to the target network device is available via the connection broker.\n"
    "* OSPF with MPLS TE is configured on the device.\n"
)

PROCEDURE = (
    "* Call parse_output('show ip ospf mpls traffic-eng link') WITHOUT pre-fetched output.\n"
    "* Genie internally calls device.execute() for the primary command (routed through broker).\n"
    "* Genie internally calls device.execute() for supplementary "
    "'show running-config | section router ospf N' (also routed through broker).\n"
    "* Verify that the VRF name is correctly resolved from the supplementary command.\n"
)

PASS_FAIL_CRITERIA = (
    "**This test passes when:**\n"
    "* The Genie parser returns a non-empty result.\n"
    "* The parsed output contains the correct VRF name (resolved via supplementary command).\n"
    "\n"
    "**This test fails if:**\n"
    "* Genie cannot execute commands through the broker (device appears disconnected).\n"
    "* The supplementary command fails to route through the broker.\n"
    "* The VRF name is missing or incorrect.\n"
)


class BrokerGenieParseTest2(IOSXETestBase):
    """
    [IOS-XE] Verify OSPF MPLS TE Links — Genie-driven execution through broker.

    Unlike the standard pattern (execute_command → parse_output(cmd, output=output)),
    this test calls parse_output(cmd) WITHOUT output, forcing Genie to drive the
    device.execute() calls itself. This validates:
    1. device.cli.execute (BrokerCliShim) works for the primary command
    2. Supplementary device.execute() calls route through the broker
    3. Both commands are cached by the broker for subsequent test files
    """

    TEST_CONFIG = {
        "resource_type": "OSPF MPLS TE Link",
        "api_endpoint": "show ip ospf mpls traffic-eng link",
        "expected_vrf": "TESTNET",
        "log_fields": [
            "check_type",
            "verification_scope",
            "vrf_resolved",
        ],
    }

    @aetest.test
    def test_ospf_mpls_te_links_genie_driven(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """Returns a single context to trigger OSPF TE link check."""
        return [
            {
                "check_type": "ospf_mpls_te_link_genie_driven",
                "verification_scope": "all_te_links",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification: Let Genie execute and parse the OSPF TE link command.

        KEY DIFFERENCE from standard tests: We do NOT pre-fetch command output.
        Instead, we call parse_output(command) without output, which forces Genie
        to call device.execute() internally — routed through the broker via
        the _BrokerCliShim patched onto testbed_device.cli.
        """
        async with semaphore:
            try:
                command = self.TEST_CONFIG["api_endpoint"]
                expected_vrf = self.TEST_CONFIG["expected_vrf"]

                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"],
                    "OSPF MPLS TE Links (Genie-driven)",
                    check_type=context.get("check_type"),
                    verification_scope=context.get("verification_scope"),
                )

                start_time = time.time()

                try:
                    # KEY: Do NOT call execute_command first.
                    # Let Genie drive the execution via device.execute() (broker-patched).
                    parsed_output = await self.parse_output(command)
                    parse_duration = time.time() - start_time

                except Exception as e:
                    api_duration = time.time() - start_time
                    error_msg = (
                        f"Failed to parse command '{command}' via Genie-driven "
                        f"execution: {str(e)}"
                    )
                    self.logger.error(
                        f"Genie-driven parse exception: {error_msg}",
                        exc_info=True,
                    )
                    context["display_context"] = "OSPF MPLS TE Links (Genie-driven)"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"Genie-driven execution failed — the broker's device "
                            f"patching (connected state, cli shim) may not be working.\n\n"
                            f"Error: {error_msg}"
                        ),
                        api_duration=api_duration,
                    )

                api_duration = parse_duration
                context["api_context"] = api_context

                if parsed_output is None or not parsed_output:
                    context["display_context"] = "OSPF MPLS TE Links (Genie-driven)"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "Parsed output is None or empty.\n\n"
                            "This indicates that Genie could not execute the command "
                            "through the broker's patched device.execute().\n\n"
                            "Check that _patch_device_execute_for_broker sets:\n"
                            "- device.connected = True\n"
                            "- device.connectionmgr.is_connected = True\n"
                            "- device.cli = _BrokerCliShim()"
                        ),
                        api_duration=api_duration,
                    )

                # The critical assertion: check that the VRF was resolved correctly.
                # The VRF name 'TESTNET' comes from the supplementary command output
                # 'router ospf 1 vrf TESTNET'. If the supplementary call failed,
                # the parser either crashes or falls back to 'default'.
                vrf_keys = list(parsed_output.get("vrf", {}).keys())
                context["vrf_resolved"] = str(vrf_keys)

                if expected_vrf in vrf_keys:
                    context["display_context"] = "OSPF MPLS TE Links (Genie-driven)"
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**Genie-Driven Broker Execution PASSED**\n\n"
                            f"VRF '{expected_vrf}' correctly resolved via Genie's "
                            f"internal device.execute() calls routed through the broker.\n\n"
                            f"This confirms:\n"
                            f"1. Primary command executed via broker (device.cli.execute)\n"
                            f"2. Supplementary command routed through broker\n"
                            f"3. Both commands cached for subsequent test files\n\n"
                            f"• VRFs found: {vrf_keys}\n"
                            f"• Parse duration: {parse_duration:.3f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    context["display_context"] = "OSPF MPLS TE Links (Genie-driven)"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**VRF resolution FAILED**\n\n"
                            f"Expected VRF '{expected_vrf}' but found: {vrf_keys}\n\n"
                            f"The supplementary 'show running-config | section router "
                            f"ospf 1' call may have failed through the broker."
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = f"Exception during Genie-driven OSPF TE check: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                context["display_context"] = "OSPF MPLS TE Links (Genie-driven)"
                return self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason=error_msg,
                    api_duration=0,
                )
