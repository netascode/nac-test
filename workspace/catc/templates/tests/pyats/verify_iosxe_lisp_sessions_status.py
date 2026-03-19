# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify LISP Sessions Status
-----------------------------------
This job file verifies that all LISP session peers discovered on an IOS-XE device are established ('Up') and match the expected peer addresses defined in jobfile parameters.
"""

import time
from pyats import aetest

import jmespath
from nac_test_pyats_common.iosxe import IOSXETestBase
from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify LISP Sessions Status on IOS-XE Devices"

DESCRIPTION = """This test validates the operational status of LISP (Locator/ID Separation Protocol) session peers on IOS-XE network devices. LISP enables dynamic separation of endpoint identity and location, facilitating scalable mobility and efficient routing in modern networks. By confirming that all control-plane sessions are established ('Up') to the expected peer RLOCs, this test ensures robust LISP control-plane connectivity, preventing disruptions in device communication and application performance due to session failures or misconfigurations."""

SETUP = (
    "* SSH access to the target IOS-XE network device is available.\n"
    "* Authentication credentials for the device are valid and configured.\n"
    "* LISP is configured and enabled on the device.\n"
    "* The correct set of expected LISP peer addresses (Map-Servers, Map-Resolvers, or Edge RLOCs) is provided in the jobfile parameters.\n"
)

PROCEDURE = (
    "* Establish SSH connection to the IOS-XE device.\n"
    "* Execute the CLI command: *show lisp session established*.\n"
    "* Parse the command output using Genie to obtain structured session data.\n"
    "* For EACH discovered LISP session peer in the default VRF:\n"
    "    * Extract the peer address (RLOC) and session state.\n"
    "    * Verify that the session `state` equals `Up`.\n"
    "    * Verify that the peer address matches one of the expected peer addresses defined in jobfile parameters.\n"
)

PASS_FAIL_CRITERIA = (
    "**This test passes when all of the following conditions are met:**\n"
    "\n"
    "* At least one LISP session peer is discovered in the command output.\n"
    "* ALL discovered LISP session peers are in 'Up' state.\n"
    "* ALL LISP session peers have peer addresses that match the expected peer address list from jobfile parameters.\n"
    "\n"
    "**This test fails if any of the following criteria are met:**\n"
    "\n"
    "* No LISP session peers are discovered in the default VRF.\n"
    "* ANY discovered LISP session peer is not in 'Up' state.\n"
    "* ANY LISP session peer address does not match the expected peer addresses in jobfile parameters.\n"
    "* The CLI command execution fails or returns an error.\n"
    "* The Genie parser fails to parse the command output.\n"
)


class VerifyLISPSessionsStatus(IOSXETestBase):
    """
    [IOS-XE] Verify LISP Sessions Status

    Verifies that all LISP session peers in the default VRF are 'Up' and that all peer addresses
    match the expected set of control-plane node RLOCs (or Edge RLOCs) as specified in jobfile parameters.
    """

    TEST_CONFIG = {
        "resource_type": "LISP Session",
        "api_endpoint": "show lisp session established",
        "expected_values": {
            "state": "Up",  # Genie output: "state"
            # "peer" address is validated dynamically using jobfile param 'expected_peer_addresses'
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_peers",
            "up_peers",
            "unexpected_peers",
        ],
    }

    @aetest.test
    def test_lisp_sessions_status(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """
        Returns a single context to trigger LISP Session verification.

        For NRFU tests, we don't load from data model - we simply verify the
        operational state of all discovered LISP sessions on the device.

        Returns:
            List containing a single context dictionary for the verification.
        """
        return [
            {
                "check_type": "lisp_sessions_status",
                "verification_scope": "all_lisp_sessions",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification: Discover ALL LISP session peers and verify their session state and peer address.

        Executes 'show lisp session established', parses the output using Genie,
        and verifies that all discovered peers have state='Up' AND are expected peers.

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
                    "All LISP Sessions",
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

                    context["display_context"] = "LISP Sessions -> Session Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=reason,
                        api_duration=api_duration,
                    )

                api_duration = command_duration + parse_duration

                context["api_context"] = api_context

                if parsed_output is None:
                    context["display_context"] = "LISP Sessions -> Session Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=f"Parsed output is None for command: {command}",
                        api_duration=api_duration,
                    )

                # JMESPath: get all session peer objects for default VRF, flatten structure
                # peers = {"10.1.1.1": [{...}], ...}
                peers_dict = jmespath.search("vrf.default.peers", parsed_output) or {}

                # Flatten all peer session records, preserving peer address for each record
                peer_records = []
                for peer_addr, session_list in peers_dict.items():
                    for session in session_list:
                        # Attach peer address for logging and validation
                        rec = dict(session)
                        rec["peer"] = peer_addr
                        peer_records.append(rec)

                if not peer_records:
                    context["display_context"] = "LISP Sessions -> Session Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No LISP session peers discovered in VRF 'default'.\n\n"
                            "This indicates that either:\n"
                            "• LISP control-plane is not configured or enabled on this device\n"
                            "• No LISP sessions have been established\n"
                            "• Network connectivity or configuration issues exist\n\n"
                            "Please verify:\n"
                            "• LISP is configured and enabled\n"
                            "• Network connectivity to peer Map-Servers/Resolvers exists\n"
                            "• LISP authentication (if configured) matches\n"
                            "• Peer addresses are correct and reachable"
                        ),
                        api_duration=api_duration,
                    )

                # Retrieve expected peer addresses from jobfile parameters
                expected_peer_addresses = set(
                    self.parameters.get("expected_peer_addresses", [])
                )

                expected_values = self.TEST_CONFIG["expected_values"]
                attributes_to_verify = list(expected_values.keys())  # ["state"]

                all_sessions_healthy = True
                validation_results = []
                failures = []
                up_count = 0
                unexpected_peers_count = 0
                total_peers = len(peer_records)

                for peer_record in peer_records:
                    peer_addr = jmespath.search("peer", peer_record)
                    if peer_addr is None:
                        peer_addr = "Not Found"
                    elif peer_addr == "":
                        peer_addr = "<empty>"

                    item_failures = []

                    # Check 'state'
                    for attr_key in attributes_to_verify:
                        actual_value = jmespath.search(attr_key, peer_record)
                        if actual_value is None:
                            actual_value = "Not Found"
                        elif actual_value == "":
                            actual_value = "<empty>"
                        expected_value = expected_values[attr_key]
                        if str(actual_value) != str(expected_value):
                            item_failures.append(
                                f"  • {attr_key}: Expected '{expected_value}', got '{actual_value}'"
                            )

                    # Check peer address match (against jobfile param)
                    if peer_addr not in expected_peer_addresses:
                        item_failures.append(
                            f"  • peer: Peer address '{peer_addr}' is not in expected_peer_addresses: {sorted(expected_peer_addresses)}"
                        )
                        unexpected_peers_count += 1

                    if item_failures:
                        all_sessions_healthy = False
                        failure_detail = (
                            f"**LISP Peer '{peer_addr}'**\n"
                            f"  Status: FAILED\n"
                            f"  Failures:\n" + "\n".join(item_failures)
                        )
                        failures.append(failure_detail)

                        # Build summary with explicit value checks
                        session_status_values = []
                        for attr in attributes_to_verify:
                            val = jmespath.search(attr, peer_record)
                            if val is None:
                                val = "Not Found"
                            elif val == "":
                                val = "<empty>"
                            session_status_values.append(f"{attr}={val}")
                        validation_results.append(
                            f"❌ {peer_addr} - " + ", ".join(session_status_values)
                        )
                    else:
                        up_count += 1
                        session_status_values = []
                        for attr in attributes_to_verify:
                            val = jmespath.search(attr, peer_record)
                            if val is None:
                                val = "Not Found"
                            elif val == "":
                                val = "<empty>"
                            session_status_values.append(f"{attr}={val}")
                        validation_results.append(
                            f"✅ {peer_addr} - " + ", ".join(session_status_values)
                        )

                # Update context with metrics
                context["total_peers"] = total_peers
                context["up_peers"] = up_count
                context["unexpected_peers"] = unexpected_peers_count

                result_summary = "\n".join(validation_results)

                if all_sessions_healthy:
                    context["display_context"] = "LISP Sessions -> Session Status"
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**LISP Session Check PASSED**\n\n"
                            f"All {total_peers} discovered LISP session peers in VRF 'default' are in 'Up' state and match expected peer addresses.\n\n"
                            f"• All sessions are established and control-plane communication is active.\n"
                            f"• All peer addresses are correct as per jobfile parameters.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**LISP Session Status:**\n"
                            f"• Total discovered peers: {total_peers}\n"
                            f"• Sessions in 'Up' state: {up_count}\n"
                            f"• Unexpected peer addresses: 0\n"
                            f"• All sessions healthy: Yes\n"
                            f"• Command execution duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    context["display_context"] = "LISP Sessions -> Session Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**LISP Session Check FAILED**\n\n"
                            f"One or more LISP session peers in VRF 'default' are not in 'Up' state, or peer addresses are unexpected.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Detailed Failures:**\n"
                            f"{chr(10).join(failures)}\n\n"
                            f"**LISP Session Status:**\n"
                            f"• Total discovered peers: {total_peers}\n"
                            f"• Sessions in 'Up' state: {up_count}\n"
                            f"• Unexpected peer addresses: {unexpected_peers_count}\n\n"
                            f"**Please verify:**\n"
                            f"• LISP is configured and enabled\n"
                            f"• Network connectivity to CP node RLOCs or Edge RLOCs exists\n"
                            f"• Peer addresses are correct and included in jobfile parameters\n"
                            f"• LISP authentication and configuration matches across devices\n"
                            f"• Command execution duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = f"Exception during LISP session check: {str(e)}"
                self.logger.error(
                    f"Exception for LISP Session Check: {error_msg}",
                    exc_info=True,
                )
                context["display_context"] = "LISP Sessions -> Session Status"
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
