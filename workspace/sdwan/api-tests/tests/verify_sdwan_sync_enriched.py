# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify All SD-WAN Edge Configurations Are In-Sync (Enriched Results)
----------------------------------------------------------------------------
This is an ENRICHED version of verify_sdwan_sync.py that demonstrates how to
store additional data in pyATS results.json using native pyATS mechanisms:

1. `runtime.reporter.client.add_extra()` - Adds data to the TestSection's `extra` field
2. `self.passed(data={...})` / `self.failed(data={...})` - Adds data to result.data

This allows the HTML report generator to access command outputs, API payloads,
and test metadata directly from results.json without relying on JSONL files.

MECHANISMS DEMONSTRATED:
- test_metadata in extra: Title, description, setup, procedure, pass/fail criteria
- command_executions in extra: API call details (endpoint, response, timing)
- verification_summary in result.data: Structured verification results

RESULTS.JSON LOCATION:
- extra field: report.tasks[0].sections[0].sections[N].extra
- result.data: report.tasks[0].sections[0].sections[N].result.data
"""

import time
from datetime import datetime

import jmespath
from nac_test_pyats_common.sdwan import SDWANManagerTestBase
from pyats import aetest
from pyats.easypy import runtime

from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify All SD-WAN Edge Configurations Are In-Sync (Enriched)"

DESCRIPTION = """This test validates configuration synchronization status for all managed SD-WAN edge devices
by querying the SD-WAN Manager REST API. SD-WAN edge devices must have a configured system IP and be in a managed
state to ensure that intended configurations are properly applied and running. Configuration synchronization is
critical for device stability, security policy enforcement, and consistent application performance across the SD-WAN fabric.

**This is an ENRICHED version** that demonstrates storing command/API execution data in results.json."""

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
    "* **Store command execution and verification data in results.json for report generation.**\n"
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


def _truncate_output(data: str | dict, max_chars: int = 50000) -> str | dict:
    """Truncate output to prevent excessive results.json size.

    Args:
        data: String or dict to potentially truncate
        max_chars: Maximum characters allowed

    Returns:
        Truncated data with indicator if truncation occurred
    """
    if isinstance(data, dict):
        # For dicts, convert to string, truncate, note it was truncated
        import json

        json_str = json.dumps(data, indent=2, default=str)
        if len(json_str) > max_chars:
            return {
                "_truncated": True,
                "_original_size": len(json_str),
                "_preview": json_str[:max_chars] + "\n... [TRUNCATED]",
            }
        return data
    elif isinstance(data, str):
        if len(data) > max_chars:
            return data[:max_chars] + "\n... [TRUNCATED]"
        return data
    return data


class VerifySDWANManagerEdgeConfigSyncEnriched(SDWANManagerTestBase):
    """
    [SDWAN-Manager] Verify All SD-WAN Edge Configurations Are In-Sync (Enriched)

    This ENRICHED test demonstrates storing additional data in results.json:
    - Test metadata (title, description, criteria) in the `extra` field
    - Command/API execution details in the `extra` field
    - Verification results summary in `result.data`

    The data stored here can be consumed by the HTML report generator to show
    command outputs and API responses without relying on JSONL files.
    """

    TEST_CONFIG = {
        "resource_type": "SDWAN Edge Configuration Sync Status",
        "api_endpoint": "/dataservice/system/device/vedges",
        "expected_values": {
            "configStatusMessage": "In Sync",
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_edge_devices",
            "healthy_edge_devices",
            "unhealthy_edge_devices",
        ],
    }

    @classmethod
    def _add_test_metadata_to_extra(cls) -> None:
        """Add pre-rendered test metadata to results.json extra field.

        This stores the test's title, description, setup, procedure, and
        pass/fail criteria in the extra field so the HTML report generator
        can access this metadata directly from results.json.

        Location in results.json:
            report.tasks[0].sections[0].sections[N].extra.test_metadata
        """
        try:
            # Get pre-rendered metadata from base class
            metadata = cls.get_rendered_metadata()

            # Add to extra field
            runtime.reporter.client.add_extra(
                test_metadata={
                    "title": metadata.get("title", TITLE),
                    "description_html": metadata.get("description_html", ""),
                    "setup_html": metadata.get("setup_html", ""),
                    "procedure_html": metadata.get("procedure_html", ""),
                    "criteria_html": metadata.get("criteria_html", ""),
                    "enriched_version": True,
                    "enrichment_timestamp": datetime.now().isoformat(),
                }
            )
        except Exception as e:
            # Don't fail the test if metadata addition fails
            import logging

            logging.getLogger(__name__).warning(
                f"Failed to add test metadata to extra: {e}"
            )

    def _add_command_execution_to_extra(
        self,
        endpoint: str,
        method: str,
        response_code: int,
        response_data: dict | str | None,
        duration: float,
        context: dict | None = None,
    ) -> None:
        """Add command/API execution details to results.json extra field.

        This stores the API call details so the HTML report generator can
        show command outputs directly from results.json.

        Args:
            endpoint: API endpoint called
            method: HTTP method (GET, POST, etc.)
            response_code: HTTP response status code
            response_data: Response body (will be truncated if too large)
            duration: API call duration in seconds
            context: Optional additional context

        Location in results.json:
            report.tasks[0].sections[0].sections[N].extra.command_executions
        """
        try:
            # Build command execution record
            execution_record = {
                "device_name": "SDWAN Manager",
                "command_type": "API",
                "method": method,
                "endpoint": endpoint,
                "full_url": f"{self.controller_url}{endpoint}",
                "response_code": response_code,
                "response_data": _truncate_output(response_data)
                if response_data
                else None,
                "duration_seconds": round(duration, 3),
                "timestamp": datetime.now().isoformat(),
                "test_context": context,
            }

            # Add to extra field - note: add_extra merges, so we use a list
            # to allow multiple command executions to be accumulated
            runtime.reporter.client.add_extra(command_executions=[execution_record])

        except Exception as e:
            self.logger.warning(f"Failed to add command execution to extra: {e}")

    @aetest.test
    def test_edge_config_sync(self, steps):
        """Entry point - delegates to base class orchestration.

        ENRICHMENT: Adds test metadata to extra field before running verification.
        """
        # Add test metadata to results.json extra field
        self._add_test_metadata_to_extra()

        # Run the standard verification flow
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

        ENRICHMENT: Stores API execution details in extra field and verification
        summary in result.data.
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

                # ENRICHMENT: Store the API call details in results.json
                response_json = None
                try:
                    response_json = response.json()
                except Exception:
                    response_json = {"_raw_text": response.text[:10000]}

                self._add_command_execution_to_extra(
                    endpoint=url,
                    method="GET",
                    response_code=response.status_code,
                    response_data=response_json,
                    duration=api_duration,
                    context={"api_context": api_context},
                )

                if response.status_code != 200:
                    context["display_context"] = (
                        f"{self.TEST_CONFIG['resource_type']} -> Configuration Sync Status"
                    )

                    # ENRICHMENT: Build verification summary for result.data
                    verification_summary = {
                        "status": "FAILED",
                        "failure_type": "api_error",
                        "http_status_code": response.status_code,
                        "endpoint": url,
                        "devices_checked": 0,
                        "devices_in_sync": 0,
                        "devices_out_of_sync": 0,
                    }

                    result = self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"API Error: Failed to query SDWAN Edge Configuration Sync Status "
                            f"(HTTP {response.status_code})\n\n"
                            f"Failed to retrieve device configuration status from endpoint: {self.TEST_CONFIG['api_endpoint']}\n\n"
                            "Please verify:\n"
                            "* The SDWAN Manager controller is reachable and responding\n"
                            "* Authentication credentials are valid\n"
                            "* The API endpoint is accessible\n"
                            "* Network connectivity to SDWAN Manager is available"
                        ),
                        api_duration=api_duration,
                    )
                    # Add verification_summary to result for result.data
                    result["verification_summary"] = verification_summary
                    return result

                data = response_json

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

                    verification_summary = {
                        "status": "FAILED",
                        "failure_type": "no_devices_found",
                        "devices_checked": 0,
                        "devices_in_sync": 0,
                        "devices_out_of_sync": 0,
                        "filter_criteria": "configuredSystemIP present AND managed-by != 'Unmanaged'",
                    }

                    result = self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No managed SDWAN edge devices with a configured system IP were discovered.\n\n"
                            "Validation requires at least one edge device that is managed and has a configured system IP.\n\n"
                            "Possible issues:\n"
                            "* No edge devices onboarded/configured\n"
                            "* Devices are not managed by a configuration group or template\n"
                            "* Devices missing 'configuredSystemIP' attribute\n\n"
                            "Please verify:\n"
                            "* Edge devices are properly onboarded and assigned a system IP\n"
                            "* Devices are managed (not in 'Unmanaged' state)\n"
                            "* Device discovery is complete"
                        ),
                        api_duration=api_duration,
                    )
                    result["verification_summary"] = verification_summary
                    return result

                expected_values = self.TEST_CONFIG["expected_values"]
                attributes_to_verify = expected_values.keys()

                all_items_healthy = True
                validation_results = []
                failures = []
                healthy_count = 0
                unhealthy_count = 0

                # ENRICHMENT: Collect per-device results for result.data
                device_results = []

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

                    # ENRICHMENT: Build per-device result record
                    device_result = {
                        "device_id": device_id,
                        "system_ip": system_ip,
                        "managed_by": mgmt_by,
                        "config_status": jmespath.search("configStatusMessage", item),
                        "status": "FAILED" if item_failures else "PASSED",
                        "failures": item_failures if item_failures else None,
                    }
                    device_results.append(device_result)

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

                # ENRICHMENT: Build comprehensive verification summary for result.data
                verification_summary = {
                    "status": "PASSED" if all_items_healthy else "FAILED",
                    "devices_checked": len(items_to_check),
                    "devices_in_sync": healthy_count,
                    "devices_out_of_sync": unhealthy_count,
                    "api_duration_seconds": round(api_duration, 3),
                    "device_results": device_results,
                    "expected_values": dict(expected_values),
                }

                if all_items_healthy:
                    context["display_context"] = (
                        f"{self.TEST_CONFIG['resource_type']} -> Configuration Sync Status"
                    )
                    result = self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**SDWAN Edge Configuration Sync Status Check PASSED**\n\n"
                            f"All {len(items_to_check)} managed SDWAN edge devices with a configured system IP "
                            f"have configuration status 'In Sync'.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Edge Configuration Sync Status:**\n"
                            f"* Total checked devices: {len(items_to_check)}\n"
                            f"* Devices 'In Sync': {healthy_count}\n"
                            f"* Devices out-of-sync: 0\n"
                            f"* All managed edges are in sync: Yes\n"
                            f"* API query duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                    result["verification_summary"] = verification_summary
                    return result
                else:
                    context["display_context"] = (
                        f"{self.TEST_CONFIG['resource_type']} -> Configuration Sync Status"
                    )
                    failures_text = "\n".join(failures)

                    # Add failure details to verification summary
                    verification_summary["failures"] = failures

                    result = self.format_verification_result(
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
                            f"* Total checked devices: {len(items_to_check)}\n"
                            f"* Devices 'In Sync': {healthy_count}\n"
                            f"* Devices out-of-sync: {unhealthy_count}\n\n"
                            f"**Please verify:**\n"
                            f"* Devices have completed configuration push\n"
                            f"* Devices are online and reachable\n"
                            f"* No configuration push failures or errors\n"
                            f"* Configuration groups/templates are correctly applied\n"
                            f"* Device 'configStatusMessage' is not empty or in 'Out-of-Sync' state\n"
                            f"* API query duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                    result["verification_summary"] = verification_summary
                    return result

            except Exception as e:
                error_msg = f"Exception during edge configuration sync check: {str(e)}"
                self.logger.error(
                    f"Exception for SDWAN Edge Configuration Sync Status Check: {error_msg}",
                    exc_info=True,
                )
                context["display_context"] = (
                    f"{self.TEST_CONFIG['resource_type']} -> Configuration Sync Status"
                )

                verification_summary = {
                    "status": "ERRORED",
                    "failure_type": "exception",
                    "error_message": str(e),
                    "devices_checked": 0,
                }

                reason = (
                    f"PyATS Framework Exception: {error_msg}\n\n"
                    f"This is a PyATS code issue, not an issue with your data model, "
                    f"SD-WAN configuration, or your network devices.\n\n"
                    f"Please contact Cisco TAC for support with this error."
                )
                result = self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason=reason,
                    api_duration=0,
                )
                result["verification_summary"] = verification_summary
                return result
