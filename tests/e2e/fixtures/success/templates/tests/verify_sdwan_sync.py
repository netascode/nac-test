# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify All SD-WAN Edge Configurations Are In-Sync
------------------------------------
This job file verifies that all managed SD-WAN edge devices with an assigned system IP
have their configuration synchronized with the SD-WAN Manager using the REST API.
"""

import time

import jmespath
from nac_test_pyats_common.sdwan import SDWANManagerTestBase
from pyats import aetest

from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify All SD-WAN Edge Configurations Are In-Sync"

DESCRIPTION = """This test validates configuration synchronization status for all managed SD-WAN edge devices
by querying the SD-WAN Manager REST API. SD-WAN edge devices must have a configured system IP and be in a managed
state to ensure that intended configurations are properly applied and running. Configuration synchronization is
critical for device stability, security policy enforcement, and consistent application performance across the SD-WAN fabric."""

SETUP = (
    "* Access to an active SD-WAN Manager controller is available via HTTPS API.\n"
    "* Authentication credentials for the SD-WAN Manager controller are valid and configured.\n"
    "* The SD-WAN fabric is deployed with managed edge devices that have completed onboarding.\n"
    "* Edge devices have system IPs assigned and are not in an 'Unmanaged' state.\n"
)

PROCEDURE = (
    "* Establish HTTPS connection to the SD-WAN Manager controller.\n"
    "* Query the SD-WAN Manager API endpoint: */dataservice/system/device/vedges*.\n"
    "* Retrieve the JSON response containing all edge device objects.\n"
    "* For EACH device object:\n"
    "    * INCLUDE device in validation scope IF `configuredSystemIP` is present AND `managed-by` != 'Unmanaged'.\n"
    "    * For each included device, verify that `configStatusMessage` equals 'In Sync'.\n"
    "    * Record devices with missing, empty, or non-'In Sync' `configStatusMessage` as unhealthy.\n"
    "* Summarize results, reporting total checked devices, healthy (in sync), and unhealthy (out-of-sync) devices.\n"
)

PASS_FAIL_CRITERIA = (
    "**This test passes when all of the following conditions are met:**\n"
    "\n"
    "* At least one SD-WAN edge device is discovered with a configured system IP and is managed.\n"
    "* For all included devices, the `configStatusMessage` attribute is present and equals 'In Sync'.\n"
    "* No device within validation scope is missing the `configStatusMessage` attribute or shows 'Out-of-Sync' or empty values.\n"
    "* The API query completes successfully and returns a valid response.\n"
    "\n"
    "**This test fails if any of the following criteria are met:**\n"
    "\n"
    "* No managed SD-WAN edge devices with a configured system IP are discovered in the API response.\n"
    "* ANY device in scope is missing the `configStatusMessage` attribute, has an empty string, or shows 'Out-of-Sync'.\n"
    "* The API query fails or returns an error response.\n"
)


class VerifySDWANManagerEdgeConfigSync(SDWANManagerTestBase):
    """
    [SDWAN-Manager] Verify All SD-WAN Edge Configurations Are In-Sync

    This test verifies that all SD-WAN edge devices with a configured system IP
    and that are managed (i.e., 'managed-by' != 'Unmanaged') have their configuration
    'In Sync'. Devices that do not have a 'configuredSystemIP' or are 'Unmanaged'
    are out of validation scope.
    """

    TEST_CONFIG = {
        "resource_type": "SDWAN Edge Configuration Sync Status",
        "api_endpoint": "/dataservice/system/device/vedges",
        "expected_values": {
            "configStatusMessage": "In Sync",  # EXACT attribute name and value per pass/fail
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_edge_devices",
            "healthy_edge_devices",
            "unhealthy_edge_devices",
        ],
    }

    @aetest.test
    def test_edge_config_sync(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """
        Returns a single context to trigger the global SDWAN edge configuration sync check.
        """
        return [
            {
                "check_type": "edge_config_sync_status",
                "verification_scope": "all_configured_and_managed_edges",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verifies that all SDWAN edge devices with a configured system IP and that are managed
        have configStatusMessage 'In Sync'.
        """
        async with semaphore:
            try:
                url = self.TEST_CONFIG["api_endpoint"]
                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"],
                    "SDWAN Edge Devices",
                    check_type=context.get("check_type"),
                    verification_scope=context.get("verification_scope"),
                )

                start_time = time.time()
                response = await client.get(url, test_context=api_context)
                api_duration = time.time() - start_time

                context["api_context"] = api_context

                if response.status_code != 200:
                    context["display_context"] = (
                        f"{self.TEST_CONFIG['resource_type']} -> Configuration Sync Status"
                    )
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"API Error: Failed to query SDWAN Edge Configuration Sync Status "
                            f"(HTTP {response.status_code})\n\n"
                            f"Failed to retrieve device configuration status from endpoint: {self.TEST_CONFIG['api_endpoint']}\n\n"
                            "Please verify:\n"
                            "• The SDWAN Manager controller is reachable and responding\n"
                            "• Authentication credentials are valid\n"
                            "• The API endpoint is accessible\n"
                            "• Network connectivity to SDWAN Manager is available"
                        ),
                        api_duration=api_duration,
                    )

                data = response.json()

                # JMESPath: Find all devices where 'configuredSystemIP' is present and 'managed-by' != 'Unmanaged'
                items_to_check = (
                    jmespath.search(
                        "data[?configuredSystemIP && \"managed-by\"!='Unmanaged']", data
                    )
                    or []
                )

                if not items_to_check:
                    context["display_context"] = (
                        f"{self.TEST_CONFIG['resource_type']} -> Configuration Sync Status"
                    )
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No managed SDWAN edge devices with a configured system IP were discovered.\n\n"
                            "Validation requires at least one edge device that is managed and has a configured system IP.\n\n"
                            "Possible issues:\n"
                            "• No edge devices onboarded/configured\n"
                            "• Devices are not managed by a configuration group or template\n"
                            "• Devices missing 'configuredSystemIP' attribute\n\n"
                            "Please verify:\n"
                            "• Edge devices are properly onboarded and assigned a system IP\n"
                            "• Devices are managed (not in 'Unmanaged' state)\n"
                            "• Device discovery is complete"
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

                for item in items_to_check:
                    item_failures = []
                    device_id = (
                        jmespath.search('"host-name"', item)
                        or jmespath.search("configuredHostname", item)
                        or jmespath.search("serialNumber", item)
                        or jmespath.search("uuid", item)
                        or "Unknown"
                    )
                    mgmt_by = jmespath.search('"managed-by"', item) or "Unknown"
                    system_ip = jmespath.search("configuredSystemIP", item) or "Unknown"

                    for attr_key in attributes_to_verify:
                        expected_value = expected_values[attr_key]
                        actual_value = jmespath.search(attr_key, item)
                        # If key is missing, treat as "Not Found" for reporting
                        actual_value_str = (
                            str(actual_value)
                            if actual_value is not None
                            else "Not Found"
                        )
                        if actual_value_str != str(expected_value):
                            item_failures.append(
                                f"Device '{device_id}' (System IP: {system_ip}, Managed-By: {mgmt_by}): "
                                f"Attribute '{attr_key}' expected '{expected_value}', found '{actual_value_str}'"
                            )

                    if item_failures:
                        all_items_healthy = False
                        unhealthy_count += 1
                        failures.extend(item_failures)
                        validation_results.append(
                            f"[FAIL] Device '{device_id}' (System IP: {system_ip}) configStatusMessage: "
                            f"{jmespath.search('configStatusMessage', item) or 'Not Found'}"
                        )
                    else:
                        healthy_count += 1
                        validation_results.append(
                            f"[PASS] Device '{device_id}' (System IP: {system_ip}) configStatusMessage: In Sync"
                        )

                context["total_edge_devices"] = len(items_to_check)
                context["healthy_edge_devices"] = healthy_count
                context["unhealthy_edge_devices"] = unhealthy_count

                result_summary = "\n".join(validation_results)

                if all_items_healthy:
                    context["display_context"] = (
                        f"{self.TEST_CONFIG['resource_type']} -> Configuration Sync Status"
                    )
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**SDWAN Edge Configuration Sync Status Check PASSED**\n\n"
                            f"All {len(items_to_check)} managed SDWAN edge devices with a configured system IP "
                            f"have configuration status 'In Sync'.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Edge Configuration Sync Status:**\n"
                            f"• Total checked devices: {len(items_to_check)}\n"
                            f"• Devices 'In Sync': {healthy_count}\n"
                            f"• Devices out-of-sync: 0\n"
                            f"• All managed edges are in sync: Yes\n"
                            f"• API query duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    context["display_context"] = (
                        f"{self.TEST_CONFIG['resource_type']} -> Configuration Sync Status"
                    )
                    failures_text = "\n".join(failures)
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**SDWAN Edge Configuration Sync Status Check FAILED**\n\n"
                            f"One or more managed SDWAN edge devices with a configured system IP "
                            f"do not have configuration status 'In Sync'.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Detailed Failures:**\n"
                            f"{failures_text}\n\n"
                            f"**Edge Configuration Sync Status:**\n"
                            f"• Total checked devices: {len(items_to_check)}\n"
                            f"• Devices 'In Sync': {healthy_count}\n"
                            f"• Devices out-of-sync: {unhealthy_count}\n\n"
                            f"**Please verify:**\n"
                            f"• Devices have completed configuration push\n"
                            f"• Devices are online and reachable\n"
                            f"• No configuration push failures or errors\n"
                            f"• Configuration groups/templates are correctly applied\n"
                            f"• Device 'configStatusMessage' is not empty or in 'Out-of-Sync' state\n"
                            f"• API query duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = f"Exception during edge configuration sync check: {str(e)}"
                self.logger.error(
                    f"Exception for SDWAN Edge Configuration Sync Status Check: {error_msg}",
                    exc_info=True,
                )
                context["display_context"] = (
                    f"{self.TEST_CONFIG['resource_type']} -> Configuration Sync Status"
                )
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
