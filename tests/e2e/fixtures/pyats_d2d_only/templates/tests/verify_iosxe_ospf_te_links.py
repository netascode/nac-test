# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify OSPF MPLS TE Links (Supplementary Parse PoC)
------------------------------------------------------------
This test verifies OSPF MPLS Traffic Engineering links by parsing
'show ip ospf mpls traffic-eng link'. The Genie parser for this command
fires a supplementary 'show running-config | section router ospf {N}' call
to resolve VRF names from OSPF process IDs.

PURPOSE: This test acts as a proof-of-concept to verify that Genie's
internal device.execute() calls work correctly when using the connection
broker. If the broker does not route supplementary commands, the parser
cannot resolve VRF names and the test will FAIL.
"""

import time

from nac_test_pyats_common.iosxe import IOSXETestBase
from pyats import aetest

from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify OSPF MPLS TE Links (Supplementary Parse PoC)"

DESCRIPTION = """This test validates OSPF MPLS Traffic Engineering link state
by parsing 'show ip ospf mpls traffic-eng link'. The Genie parser internally
calls 'show running-config | section router ospf N' to resolve which VRF each
OSPF instance belongs to. This test verifies that supplementary device.execute()
calls work correctly through the connection broker."""

SETUP = (
    "* SSH access to the target network device is available.\n"
    "* OSPF with MPLS TE is configured on the device.\n"
)

PROCEDURE = (
    "* Execute 'show ip ospf mpls traffic-eng link' via connection broker.\n"
    "* Parse the output using Genie (which internally calls "
    "'show running-config | section router ospf N').\n"
    "* Verify that the VRF name is correctly resolved from the supplementary command.\n"
)

PASS_FAIL_CRITERIA = (
    "**This test passes when:**\n"
    "* The Genie parser returns a non-empty result.\n"
    "* The parsed output contains the correct VRF name (resolved via supplementary command).\n"
    "\n"
    "**This test fails if:**\n"
    "* Parsing fails because supplementary device.execute() calls cannot reach the device.\n"
    "* The VRF name is missing or incorrect (e.g., 'default' instead of the actual VRF).\n"
)


class VerifyOspfMplsTeLinks(IOSXETestBase):
    """
    [IOS-XE] Verify OSPF MPLS TE Links — PoC for supplementary parse fix.

    Parses 'show ip ospf mpls traffic-eng link' which internally triggers
    'show running-config | section router ospf {N}' to resolve VRF names.
    On current main (without the broker execute patch), this test FAILS
    because the supplementary device.execute() call cannot reach the device.
    """

    TEST_CONFIG = {
        "resource_type": "OSPF MPLS TE Link",
        "api_endpoint": "show ip ospf mpls traffic-eng link",
        # VRF expected from supplementary command parsing
        "expected_vrf": "TESTNET",
        "log_fields": [
            "check_type",
            "verification_scope",
            "vrf_resolved",
        ],
    }

    @aetest.test
    def test_ospf_mpls_te_links(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """Returns a single context to trigger OSPF TE link check."""
        return [
            {
                "check_type": "ospf_mpls_te_link",
                "verification_scope": "all_te_links",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification: Execute and parse OSPF TE link command.

        The key assertion is that the parsed output contains the correct VRF
        name ('TESTNET'), which can only be resolved if the parser's
        supplementary device.execute() call succeeds.
        """
        async with semaphore:
            try:
                command = self.TEST_CONFIG["api_endpoint"]
                expected_vrf = self.TEST_CONFIG["expected_vrf"]

                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"],
                    "OSPF MPLS TE Links",
                    check_type=context.get("check_type"),
                    verification_scope=context.get("verification_scope"),
                )

                start_time = time.time()

                try:
                    with self.test_context(api_context):
                        output = await self.execute_command(command)
                    command_duration = time.time() - start_time

                    parse_start = time.time()
                    parsed_output = await self.parse_output(command, output=output)
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
                    context["display_context"] = "OSPF MPLS TE Links"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"Genie parser failed — likely because the supplementary "
                            f"'show running-config | section router ospf N' call could not "
                            f"reach the device through the broker.\n\n"
                            f"Error: {error_msg}"
                        ),
                        api_duration=api_duration,
                    )

                api_duration = command_duration + parse_duration
                context["api_context"] = api_context

                # Check if parsing returned anything
                if parsed_output is None or not parsed_output:
                    context["display_context"] = "OSPF MPLS TE Links"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "Parsed output is None or empty.\n\n"
                            "This indicates that the Genie parser's supplementary "
                            "'show running-config | section router ospf N' call failed "
                            "because device.execute() is not routed through the broker.\n\n"
                            "This is the exact bug described in issue #663."
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
                    context["display_context"] = "OSPF MPLS TE Links"
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**OSPF MPLS TE Link Check PASSED**\n\n"
                            f"VRF '{expected_vrf}' correctly resolved from supplementary "
                            f"'show running-config | section router ospf 1' command.\n\n"
                            f"This confirms that Genie's internal device.execute() calls "
                            f"are correctly routed through the connection broker.\n\n"
                            f"• VRFs found: {vrf_keys}\n"
                            f"• Parse duration: {parse_duration:.3f}s\n"
                            f"• Total duration: {api_duration:.3f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    context["display_context"] = "OSPF MPLS TE Links"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**VRF resolution FAILED**\n\n"
                            f"Expected VRF '{expected_vrf}' but found: {vrf_keys}\n\n"
                            f"This means the supplementary 'show running-config | section "
                            f"router ospf 1' call either failed or returned unexpected data.\n\n"
                            f"Parsed output keys: {list(parsed_output.keys())}"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = f"Exception during OSPF TE link check: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                context["display_context"] = "OSPF MPLS TE Links"
                return self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason=error_msg,
                    api_duration=0,
                )
