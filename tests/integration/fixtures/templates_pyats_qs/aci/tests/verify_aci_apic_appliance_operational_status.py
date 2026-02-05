# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify APIC Appliance Operational Status
------------------------------------------------
This job file verifies that all APIC controllers in the ACI fabric are actively
participating in cluster operations by ensuring their operational status is "available".
"""

import time

import jmespath
from nac_test_pyats_common.aci.test_base import APICTestBase
from pyats import aetest

from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify APIC Appliance Operational Status"

DESCRIPTION = """This test validates that all Cisco APIC controllers in the ACI fabric are operational
and actively participating in cluster operations. The APIC appliance operational status
is a critical indicator of controller health, confirming that each APIC node is available
and functioning as part of the cluster. Ensuring all APICs report an 'available' status
helps maintain ACI fabric stability, supports management operations, and prevents outages
due to controller unavailability or faults.
"""

SETUP = (
    "* Access to at least one Cisco APIC controller is available.\n"
    "* Authentication credentials for the APIC REST API are valid and configured.\n"
    "* The APIC cluster is deployed and reachable in the ACI fabric.\n"
)

PROCEDURE = (
    "* Establish a connection to the Cisco APIC controller via REST API.\n"
    "* Query the APIC REST API endpoint:\n"
    '    */api/node/class/infraWiNode.json?query-target-filter=wcard(infraWiNode.dn,"topology/pod-1/node-1/")*\n'
    "* Retrieve all `infraWiNode` managed objects representing APIC controllers.\n"
    "* For EACH discovered APIC controller:\n"
    "    * Extract the controller's `nodeName`, `id`, and `addr` from the attributes.\n"
    "    * Verify the `operSt` attribute is set to `available`.\n"
    "* Log the total number of controllers discovered, number healthy (operSt='available'), and number unhealthy (operSt!='available').\n"
    "* Report the result as PASSED if all controllers are healthy; otherwise, report as FAILED with details.\n"
)

PASS_FAIL_CRITERIA = (
    "**This test passes when all of the following conditions are met:**\n"
    "\n"
    "* At least one APIC controller is discovered via the API query.\n"
    "* ALL discovered APIC controllers have the `operSt` attribute set to `available`.\n"
    "* The API query completes successfully without error.\n"
    "\n"
    "**This test fails if any of the following criteria are met:**\n"
    "\n"
    "* No APIC controllers are discovered in the API response.\n"
    "* ANY discovered APIC controller has the `operSt` attribute set to a value other than `available` (e.g., `unavailable`, `unregistered`).\n"
    "* The API query fails or returns a non-successful response.\n"
)


class VerifyApicApplianceOperationalStatus(APICTestBase):
    """
    [ACI] Verify APIC Appliance Operational Status

    Ensures all APIC controllers discovered via the APIC REST API
    have 'operSt' attribute equal to 'available'.
    """

    TEST_CONFIG = {
        "resource_type": "APIC Appliance Operational Status",
        "api_endpoint": 'node/class/infraWiNode.json?query-target-filter=wcard(infraWiNode.dn,"topology/pod-1/node-1/")',
        "expected_values": {
            "operSt": "available",  # EXACT attribute name and value from pass/fail criteria and sample API output
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
    def test_apic_appliance_oper_status(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """
        Returns a single context to trigger the global appliance operational status check.
        """
        return [
            {
                "check_type": "apic_appliance_operational_status",
                "verification_scope": "all_discovered_apic_controllers",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification logic:
        Query all infraWiNode objects and verify 'operSt' == 'available' for each APIC controller.
        """
        async with semaphore:
            try:
                url = f"/api/{self.TEST_CONFIG['api_endpoint']}"
                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"],
                    "All APIC Controllers",
                    check_type=context.get("check_type"),
                    verification_scope=context.get("verification_scope"),
                )
                start_time = time.time()
                response = await client.get(url, test_context=api_context)
                api_duration = time.time() - start_time
                context["api_context"] = api_context

                if response.status_code != 200:
                    context["display_context"] = (
                        f"{self.TEST_CONFIG['resource_type']} -> Operational Status"
                    )
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"API Error: Failed to query APIC appliance operational status (HTTP {response.status_code})\n\n"
                            f"Failed to retrieve operational status from endpoint: {self.TEST_CONFIG['api_endpoint']}\n\n"
                            "Please verify:\n"
                            "• The APIC controller is reachable and responding\n"
                            "• Authentication credentials are valid\n"
                            "• The API endpoint is accessible\n"
                            "• Network connectivity to the APIC is available"
                        ),
                        api_duration=api_duration,
                    )

                data = response.json()
                # Extract the list of all infraWiNode attributes objects
                appliances = (
                    jmespath.search("imdata[].infraWiNode.attributes", data) or []
                )

                if not appliances:
                    context["display_context"] = (
                        f"{self.TEST_CONFIG['resource_type']} -> Operational Status"
                    )
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No APIC appliances discovered.\n\n"
                            "This indicates that either:\n"
                            "• The APIC system is not properly initialized\n"
                            "• The API query returned no results\n"
                            "• There is a configuration or discovery issue\n\n"
                            "Please verify:\n"
                            "• At least one APIC controller is registered in the fabric\n"
                            "• The APIC discovery process is complete\n"
                            "• The API credentials and endpoint are correct"
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

                for appliance in appliances:
                    node_name = jmespath.search("nodeName", appliance) or "Not Found"
                    node_id = jmespath.search("id", appliance) or "Not Found"
                    node_addr = jmespath.search("addr", appliance) or "Not Found"
                    item_failures = []
                    item_status_values = []

                    for attr_key in attributes_to_verify:
                        actual_value = (
                            jmespath.search(attr_key, appliance) or "Not Found"
                        )
                        expected_value = expected_values[attr_key]
                        item_status_values.append(f"{attr_key}={actual_value}")
                        if str(actual_value) != str(expected_value):
                            item_failures.append(
                                f"  • {attr_key}: Expected '{expected_value}', got '{actual_value}'"
                            )

                    if item_failures:
                        all_items_healthy = False
                        unhealthy_count += 1
                        failure_detail = (
                            f"**APIC Controller: {node_name}**\n"
                            f"  ID: {node_id}\n"
                            f"  Address: {node_addr}\n"
                            f"  Status: UNAVAILABLE\n"
                            f"  Failures:\n" + "\n".join(item_failures)
                        )
                        failures.append(failure_detail)
                        validation_results.append(
                            f"[FAIL] {node_name} (ID: {node_id}) - "
                            + ", ".join(item_status_values)
                        )
                    else:
                        healthy_count += 1
                        validation_results.append(
                            f"[PASS] {node_name} (ID: {node_id}) - "
                            + ", ".join(item_status_values)
                        )

                context["total_items"] = len(appliances)
                context["healthy_items"] = healthy_count
                context["unhealthy_items"] = unhealthy_count

                result_summary = "\n".join(validation_results)
                context["display_context"] = (
                    f"{self.TEST_CONFIG['resource_type']} -> Operational Status"
                )

                if all_items_healthy:
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**APIC Appliance Operational Status Check PASSED**\n\n"
                            f"All {len(appliances)} discovered APIC controllers have 'operSt' attribute set to 'available'.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**APIC Appliance Status:**\n"
                            f"• Total discovered controllers: {len(appliances)}\n"
                            f"• Controllers with operSt='available': {healthy_count}\n"
                            f"• All controllers actively participating in cluster operations: Yes\n"
                            f"• API query duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    failures_text = '\n'.join(failures)
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**APIC Appliance Operational Status Check FAILED**\n\n"
                            f"One or more discovered APIC controllers do not have 'operSt' set to 'available'.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Detailed Failures:**\n"
                            f"{failures_text}\n\n"
                            f"**APIC Appliance Status:**\n"
                            f"• Total discovered controllers: {len(appliances)}\n"
                            f"• Controllers with operSt='available': {healthy_count}\n"
                            f"• Controllers with operSt!='available': {unhealthy_count}\n\n"
                            f"**Please verify:**\n"
                            f"• All APIC controllers are powered on and operational\n"
                            f"• No APICs are in maintenance or fault state\n"
                            f"• Network connectivity to all APIC controllers is available\n"
                            f"• The cluster formation process completed successfully\n"
                            f"• No controllers are in standby or unregistered\n"
                            f"• Hardware is properly seated and recognized"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = f"Exception during APIC appliance operational status check: {str(e)}"
                self.logger.error(
                    f"Exception for APIC Appliance Operational Status Check: {error_msg}",
                    exc_info=True,
                )
                context["display_context"] = (
                    f"{self.TEST_CONFIG['resource_type']} -> Operational Status"
                )
                reason = (
                    f"PyATS Framework Exception: {error_msg}\n\n"
                    f"This is a PyATS code issue, not an issue with your data model, "
                    f"ACI as Code configuration, or your ACI fabric.\n\n"
                    f"Please contact Cisco TAC for support with this error."
                )
                return self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason=reason,
                    api_duration=0,
                )
