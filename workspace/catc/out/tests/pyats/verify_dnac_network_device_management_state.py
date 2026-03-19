# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify DNAC Network Device Management State
--------------------------------------------------
This job file verifies that all network devices discovered by Cisco Catalyst Center
(DNA Center) have both `managementState` and `collectionStatus` set to 'Managed',
ensuring devices are fully onboarded and operational.
"""

import time
from pyats import aetest

import jmespath
from nac_test_pyats_common.catc import CatalystCenterTestBase
from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify Network Device Management State in Catalyst Center"

DESCRIPTION = """This test validates that all network devices discovered by Cisco Catalyst Center
are fully managed. The attributes `managementState` and `collectionStatus` reflect the
device's onboarding and inventory collection status.

Ensuring both are set to 'Managed' confirms that:
- Catalyst Center has successfully discovered, onboarded, and established management connectivity
- Inventory collection and monitoring are operational for each device

This validation is critical for network stability, allowing consistent configuration,
monitoring, and assurance across the managed device inventory."""

SETUP = (
    "* Access to an active Cisco Catalyst Center (DNA Center) controller via HTTPS API\n"
    "* Valid authentication credentials for Catalyst Center\n"
    "* One or more network devices have been discovered and added to the Catalyst Center inventory\n"
    "* Device discovery and inventory collection have completed successfully\n"
)

PROCEDURE = (
    "* Establish HTTPS connection to the Catalyst Center controller\n"
    "* Query the API endpoint: */dna/intent/api/v1/network-device*\n"
    "* Retrieve the list of all discovered network devices\n"
    "* For EACH device in the response:\n"
    "    * Extract the device's hostname and management IP address\n"
    "    * Extract the `managementState` and `collectionStatus` attributes\n"
    "    * Verify that both attributes are equal to 'Managed'\n"
)

PASS_FAIL_CRITERIA = (
    "**This test passes when all of the following conditions are met:**\n"
    "\n"
    "* At least one network device is discovered in Catalyst Center inventory\n"
    "* ALL discovered devices have `managementState` equal to 'Managed'\n"
    "* ALL discovered devices have `collectionStatus` equal to 'Managed'\n"
    "\n"
    "**This test fails if any of the following criteria are met:**\n"
    "\n"
    "* No network devices are discovered in the API response\n"
    "* ANY discovered device has `managementState` other than 'Managed'\n"
    "* ANY discovered device has `collectionStatus` other than 'Managed'\n"
    "* The API query fails or returns an error response\n"
)


class VerifyDnacNetworkDeviceManagementState(CatalystCenterTestBase):
    """
    [DNAC] Verify Network Device Management State

    Ensures all network devices discovered by Cisco DNA Center have
    managementState='Managed' and collectionStatus='Managed' for full
    management confirmation.
    """

    TEST_CONFIG = {
        "resource_type": "Network Device Management State",
        "api_endpoint": "/dna/intent/api/v1/network-device",
        "expected_values": {
            "managementState": "Managed",
            "collectionStatus": "Managed",
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_devices",
            "fully_managed_devices",
            "not_fully_managed_devices",
        ],
    }

    @aetest.test
    def test_network_device_management_state(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """
        Returns a single context to trigger verification of all network devices.
        """
        return [
            {
                "check_type": "dnac_network_device_management_state",
                "verification_scope": "all_network_devices",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification:
            - All network devices must have managementState='Managed'
            - All network devices must have collectionStatus='Managed'
        """
        async with semaphore:
            try:
                url = self.TEST_CONFIG["api_endpoint"]

                api_context = self.build_api_context(
                    "DNAC Network Device Management State",
                    "All Network Devices",
                    check_type=context.get("check_type"),
                    verification_scope=context.get("verification_scope"),
                )

                start_time = time.time()
                response = await client.get(url, test_context=api_context)
                api_duration = time.time() - start_time

                context["api_context"] = api_context

                if response.status_code != 200:
                    context["display_context"] = "Network Devices -> Management State"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"API Error: Failed to query network devices (HTTP {response.status_code})\n\n"
                            f"Failed to retrieve device inventory from endpoint: {self.TEST_CONFIG['api_endpoint']}\n\n"
                            "Please verify:\n"
                            "• The Catalyst Center controller is reachable and responding\n"
                            "• Authentication credentials are valid\n"
                            "• The API endpoint is accessible\n"
                            "• Network connectivity to Catalyst Center is available"
                        ),
                        api_duration=api_duration,
                    )

                data = response.json()
                devices = jmespath.search("response[*]", data) or []

                if not devices:
                    context["display_context"] = "Network Devices -> Management State"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No network devices discovered in Catalyst Center inventory.\n\n"
                            "This indicates that either:\n"
                            "• No devices have been discovered by Catalyst Center\n"
                            "• The API query returned no results\n"
                            "• Device discovery has not been performed\n\n"
                            "Please verify:\n"
                            "• Device discovery has been configured and executed\n"
                            "• Network devices are reachable from Catalyst Center\n"
                            "• SNMP/SSH credentials are properly configured\n"
                            "• Discovery IP ranges include the target devices"
                        ),
                        api_duration=api_duration,
                    )

                discovered_devices = {
                    jmespath.search("hostname", device): device
                    for device in devices
                    if jmespath.search("hostname", device)
                }

                expected_values = self.TEST_CONFIG["expected_values"]
                attributes_to_verify = expected_values.keys()

                all_fully_managed = True
                validation_results = []
                failures = []
                fully_managed_count = 0
                not_fully_managed_count = 0

                for hostname, device in discovered_devices.items():
                    mgmt_ip = jmespath.search("managementIpAddress", device)
                    if mgmt_ip is None:
                        mgmt_ip = "Not Found"
                    elif mgmt_ip == "":
                        mgmt_ip = "<empty>"

                    device_failures = []

                    for attr_key in attributes_to_verify:
                        actual_value = jmespath.search(attr_key, device)
                        if actual_value is None:
                            actual_value = "Not Found"
                        elif actual_value == "":
                            actual_value = "<empty>"

                        expected_value = expected_values[attr_key]

                        if str(actual_value) != str(expected_value):
                            device_failures.append(
                                f"  • {attr_key}: Expected '{expected_value}', got '{actual_value}'"
                            )

                    if device_failures:
                        all_fully_managed = False
                        not_fully_managed_count += 1

                        failure_detail = (
                            f"**Device: {hostname}**\n"
                            f"  Management IP: {mgmt_ip}\n"
                            f"  Status: NOT FULLY MANAGED\n"
                            f"  Failures:\n" + "\n".join(device_failures)
                        )
                        failures.append(failure_detail)

                        device_status_values = []
                        for attr in attributes_to_verify:
                            val = jmespath.search(attr, device)
                            if val is None:
                                val = "Not Found"
                            elif val == "":
                                val = "<empty>"
                            device_status_values.append(f"{attr}={val}")

                        validation_results.append(
                            f"❌ {hostname} ({mgmt_ip}) - "
                            + ", ".join(device_status_values)
                        )
                    else:
                        fully_managed_count += 1

                        device_status_values = []
                        for attr in attributes_to_verify:
                            val = jmespath.search(attr, device)
                            if val is None:
                                val = "Not Found"
                            elif val == "":
                                val = "<empty>"
                            device_status_values.append(f"{attr}={val}")

                        validation_results.append(
                            f"✅ {hostname} ({mgmt_ip}) - "
                            + ", ".join(device_status_values)
                        )

                context["total_devices"] = len(discovered_devices)
                context["fully_managed_devices"] = fully_managed_count
                context["not_fully_managed_devices"] = not_fully_managed_count

                result_summary = "\n".join(validation_results)

                if all_fully_managed:
                    context["display_context"] = "Network Devices -> Management State"
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**Network Device Management State Check PASSED**\n\n"
                            f"All {len(discovered_devices)} discovered network devices have "
                            f"managementState='Managed' and collectionStatus='Managed'.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Device Inventory Summary:**\n"
                            f"• Total discovered devices: {len(discovered_devices)}\n"
                            f"• Devices fully managed: {fully_managed_count}\n"
                            f"• All devices fully managed: Yes\n"
                            f"• API query duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    context["display_context"] = "Network Devices -> Management State"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**Network Device Management State Check FAILED**\n\n"
                            f"One or more discovered devices do not have both "
                            f"managementState='Managed' and collectionStatus='Managed'.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Detailed Failures:**\n"
                            f"{chr(10).join(failures)}\n\n"
                            f"**Device Inventory Summary:**\n"
                            f"• Total discovered devices: {len(discovered_devices)}\n"
                            f"• Devices fully managed: {fully_managed_count}\n"
                            f"• Devices NOT fully managed: {not_fully_managed_count}\n\n"
                            f"**Please verify:**\n"
                            f"• Device is reachable from Catalyst Center\n"
                            f"• SNMP/SSH credentials are correct\n"
                            f"• Device software is compatible with Catalyst Center\n"
                            f"• No device authentication failures\n"
                            f"• Network connectivity is stable\n"
                            f"• Device is not in maintenance mode"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = f"Exception during DNAC network device management state check: {str(e)}"
                self.logger.error(
                    f"Exception for DNAC Network Device Management State Check: {error_msg}",
                    exc_info=True,
                )

                context["display_context"] = "Network Devices -> Management State"

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
