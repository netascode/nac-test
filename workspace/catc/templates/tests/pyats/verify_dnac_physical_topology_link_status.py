# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify Physical Topology Link Status
--------------------------------------------------
This job file verifies that all physical topology links discovered by Cisco Catalyst Center
are operational, confirming that all device-to-device physical connections are up and healthy.
"""

import time
from pyats import aetest

import jmespath
from nac_test_pyats_common.catc import CatalystCenterTestBase
from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify Physical Topology Link Status"

DESCRIPTION = """This test validates the operational status of all physical topology links
discovered by Cisco Catalyst Center. Physical topology links represent direct physical
connections between network devices, providing essential connectivity for network traffic
and application flow.

Ensuring that all discovered links have status 'up' confirms the underlying infrastructure
is intact, cable connections are present, and interfaces are enabled and healthy. This
verification is critical for network resilience, device reachability, and overall
infrastructure stability."""

SETUP = (
    "* Access to an active Cisco Catalyst Center controller via HTTPS API.\n"
    "* Authentication credentials for Catalyst Center are valid and configured.\n"
    "* Network devices have been discovered and mapped into the physical topology.\n"
    "* Device discovery and topology mapping have completed successfully.\n"
)

PROCEDURE = (
    "* Establish HTTPS connection to the Catalyst Center controller.\n"
    "* Query the Catalyst Center API endpoint: */dna/intent/api/v1/topology/physical-topology*.\n"
    "* Retrieve the physical topology JSON response containing all discovered links.\n"
    "* Parse the JSON response and extract the `response.links[]` array.\n"
    "* For EACH discovered link:\n"
    "    * Extract source and target device UUIDs, start and end port names, and link ID.\n"
    "    * Extract the `linkStatus` attribute for the link.\n"
    "    * Verify that `linkStatus` equals 'up'.\n"
)

PASS_FAIL_CRITERIA = (
    "**This test passes when all of the following conditions are met:**\n"
    "\n"
    "* At least one physical topology link is discovered in Catalyst Center.\n"
    "* ALL discovered physical topology links have `linkStatus` equal to 'up'.\n"
    "\n"
    "**This test fails if any of the following criteria are met:**\n"
    "\n"
    "* No physical topology links are discovered in the API response.\n"
    "* ANY discovered link has `linkStatus` other than 'up' (e.g., 'down', empty, or missing).\n"
    "* The API query fails or returns an error response.\n"
)


class VerifyPhysicalTopologyLinkStatus(CatalystCenterTestBase):
    """
    [DNAC] Verify Physical Topology Link Status

    Verifies that all physical topology links discovered by Catalyst Center have
    linkStatus='up', indicating that all physical connections between devices
    are operational and healthy.
    """

    TEST_CONFIG = {
        "resource_type": "Physical Topology Link Status",
        "api_endpoint": "/dna/intent/api/v1/topology/physical-topology",
        "expected_values": {
            "linkStatus": "up",
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_links",
            "up_links",
            "down_links",
        ],
    }

    @aetest.test
    def test_physical_topology_link_status(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """
        Returns a single context to trigger the global physical link status check.

        Returns:
            List containing a single context dictionary for the verification.
        """
        return [
            {
                "check_type": "physical_topology_link_status",
                "verification_scope": "all_topology_links",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification: Discover ALL physical topology links and verify linkStatus='up'.
        Args:
            semaphore: Asyncio semaphore for concurrency control.
            client: HTTP client for making API calls.
            context: Dictionary containing check_type and verification_scope.

        Returns:
            Dictionary containing verification result with status, reason, and metadata.
        """
        async with semaphore:
            try:
                url = self.TEST_CONFIG["api_endpoint"]

                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"],
                    "All Physical Topology Links",
                    check_type=context.get("check_type"),
                    verification_scope=context.get("verification_scope"),
                )

                start_time = time.time()
                response = await client.get(url, test_context=api_context)
                api_duration = time.time() - start_time

                context["api_context"] = api_context

                if response.status_code != 200:
                    context["display_context"] = "Physical Topology -> Link Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"API Error: Failed to query physical topology links (HTTP {response.status_code})\n\n"
                            f"Failed to retrieve physical topology from endpoint: {self.TEST_CONFIG['api_endpoint']}\n\n"
                            "Please verify:\n"
                            "• The Catalyst Center controller is reachable and responding\n"
                            "• Authentication credentials are valid\n"
                            "• The API endpoint is accessible\n"
                            "• Network connectivity to Catalyst Center is available"
                        ),
                        api_duration=api_duration,
                    )

                data = response.json()
                links = jmespath.search("response.links[]", data) or []

                if not links:
                    context["display_context"] = "Physical Topology -> Link Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No physical topology links discovered in Catalyst Center.\n\n"
                            "This indicates that either:\n"
                            "• No physical links have been discovered by Catalyst Center\n"
                            "• The API query returned no results\n"
                            "• Device discovery or topology mapping has not been performed\n\n"
                            "Please verify:\n"
                            "• Device discovery has been configured and executed\n"
                            "• Devices are reachable and interconnected\n"
                            "• Topology services are running on Catalyst Center\n"
                        ),
                        api_duration=api_duration,
                    )

                expected_values = self.TEST_CONFIG["expected_values"]
                attributes_to_verify = expected_values.keys()

                all_links_up = True
                validation_results = []
                failures = []
                up_count = 0
                down_count = 0

                for link in links:
                    item_failures = []

                    # Extract relevant info for reporting
                    source = jmespath.search("source", link)
                    if source is None:
                        source = "Not Found"
                    elif source == "":
                        source = "<empty>"

                    target = jmespath.search("target", link)
                    if target is None:
                        target = "Not Found"
                    elif target == "":
                        target = "<empty>"

                    start_port = jmespath.search("startPortName", link)
                    if start_port is None:
                        start_port = "Not Found"
                    elif start_port == "":
                        start_port = "<empty>"

                    end_port = jmespath.search("endPortName", link)
                    if end_port is None:
                        end_port = "Not Found"
                    elif end_port == "":
                        end_port = "<empty>"

                    link_id = jmespath.search("id", link)
                    if link_id is None:
                        link_id = "Not Found"
                    elif link_id == "":
                        link_id = "<empty>"

                    for attr_key in attributes_to_verify:
                        actual_value = jmespath.search(attr_key, link)
                        if actual_value is None:
                            actual_value = "Not Found"
                        elif actual_value == "":
                            actual_value = "<empty>"

                        expected_value = expected_values[attr_key]

                        if str(actual_value) != str(expected_value):
                            item_failures.append(
                                f"  • {attr_key}: Expected '{expected_value}', got '{actual_value}'"
                            )

                    # Build summary for this link
                    link_summary = (
                        f"Link ID: {link_id} | Source: {source} ({start_port}) "
                        f"<-> Target: {target} ({end_port})"
                    )

                    # Build status string
                    status_values = []
                    for attr in attributes_to_verify:
                        val = jmespath.search(attr, link)
                        if val is None:
                            val = "Not Found"
                        elif val == "":
                            val = "<empty>"
                        status_values.append(f"{attr}={val}")

                    if item_failures:
                        all_links_up = False
                        down_count += 1

                        failures.append(
                            f"**{link_summary}**\n"
                            f"  Status: NOT UP\n"
                            f"  Failures:\n{chr(10).join(item_failures)}"
                        )
                        validation_results.append(
                            f"❌ {link_summary} - {', '.join(status_values)}"
                        )
                    else:
                        up_count += 1
                        validation_results.append(
                            f"✅ {link_summary} - {', '.join(status_values)}"
                        )

                context["total_links"] = len(links)
                context["up_links"] = up_count
                context["down_links"] = down_count

                result_summary = "\n".join(validation_results)

                if all_links_up:
                    context["display_context"] = "Physical Topology -> Link Status"
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**Physical Topology Link Status Check PASSED**\n\n"
                            f"All {len(links)} discovered physical topology links are operational (linkStatus='up').\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Physical Topology Link Status:**\n"
                            f"• Total discovered links: {len(links)}\n"
                            f"• Links with linkStatus='up': {up_count}\n"
                            f"• All links up: Yes\n"
                            f"• API query duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    context["display_context"] = "Physical Topology -> Link Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**Physical Topology Link Status Check FAILED**\n\n"
                            f"One or more discovered physical topology links are NOT up.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Detailed Failures:**\n"
                            f"{chr(10).join(failures)}\n\n"
                            f"**Physical Topology Link Status:**\n"
                            f"• Total discovered links: {len(links)}\n"
                            f"• Links with linkStatus='up': {up_count}\n"
                            f"• Links NOT up: {down_count}\n\n"
                            f"**Please verify:**\n"
                            f"• Cable connections between devices are intact\n"
                            f"• Interfaces on both ends are enabled and operational\n"
                            f"• No hardware faults or misconfigurations\n"
                            f"• Devices are reachable and not in maintenance or error state\n"
                            f"• Topology information is up to date in Catalyst Center\n"
                            f"• API query duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = (
                    f"Exception during physical topology link status check: {str(e)}"
                )
                self.logger.error(
                    f"Exception for Physical Topology Link Status Check: {error_msg}",
                    exc_info=True,
                )

                context["display_context"] = "Physical Topology -> Link Status"

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
