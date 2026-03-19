# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify Catalyst Center System Health - No Critical Events
-----------------------------------------------------------------
This job file verifies that all system health events reported by Cisco Catalyst Center
do not have critical severity or state, ensuring there are no active critical issues.
"""

import time
from pyats import aetest

import jmespath
from nac_test_pyats_common.catc import CatalystCenterTestBase
from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify Catalyst Center System Health - No Critical Events"

DESCRIPTION = """This test checks the overall health status of the Cisco Catalyst Center controller
by verifying that no system health events are reported as critical. The system health events
API provides real-time visibility into the status of controller subsystems and infrastructure.

A critical event (severity=1 or state='Critical') may indicate major controller faults,
service outages, or infrastructure failures that could impact network automation, device
management, and application assurance. Validating the absence of critical events confirms
controller stability and reliable operation for dependent network services."""

SETUP = (
    "* Access to a functioning Cisco Catalyst Center controller via HTTPS API.\n"
    "* Authentication credentials for Catalyst Center are valid and configured.\n"
    "* The Catalyst Center system and its diagnostics subsystem are operational and enabled.\n"
)

PROCEDURE = (
    "* Establish HTTPS connection to the Cisco Catalyst Center controller.\n"
    "* Query the Catalyst Center API endpoint:\n"
    "    */dna/intent/api/v1/diagnostics/system/health?summary=true*\n"
    "* Parse the JSON response and extract the array of `healthEvents`.\n"
    "* For EACH reported system health event:\n"
    "    * Extract the `hostname`, `instance`, `description`, `severity`, and `state` attributes.\n"
    "    * Verify that `severity` is NOT equal to 1 (critical).\n"
    "    * Verify that `state` is NOT equal to 'Critical'.\n"
    "* Record the total number of events, and count how many are non-critical vs. critical.\n"
)

PASS_FAIL_CRITERIA = (
    "**This test passes when all of the following conditions are met:**\n"
    "\n"
    "* At least one system health event is reported by the Catalyst Center API.\n"
    "* ALL reported system health events have `severity` not equal to 1 AND `state` not equal to 'Critical'.\n"
    "\n"
    "**This test fails if any of the following criteria are met:**\n"
    "\n"
    "* No system health events are discovered in the API response.\n"
    "* ANY event has `severity` equal to 1 (critical).\n"
    "* ANY event has `state` equal to 'Critical'.\n"
    "* The API query fails, returns an error response, or is inaccessible.\n"
)


class VerifyCatalystCenterSystemHealthNoCriticalEvents(CatalystCenterTestBase):
    """
    [DNAC] Verify Catalyst Center System Health - No Critical Events

    Verifies that all system health events reported by Catalyst Center do not have
    severity=1 (Critical) or state="Critical". The test passes if no events are critical,
    otherwise it fails and provides detailed failure information.
    """

    TEST_CONFIG = {
        "resource_type": "Catalyst Center System Health Events",
        "api_endpoint": "/dna/intent/api/v1/diagnostics/system/health?summary=true",
        "expected_values": {
            "severity": "NOT 1",  # Pass if severity != 1
            "state": "NOT Critical",  # Pass if state != "Critical"
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_events",
            "non_critical_events",
            "critical_events",
        ],
    }

    @aetest.test
    def test_system_health_no_critical_events(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """
        Returns a single context to trigger global system health event check.
        """
        return [
            {
                "check_type": "system_health_event_check",
                "verification_scope": "all_health_events",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification: Discover ALL system health events and verify no events are critical.
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
                    "Global System Health",
                    check_type=context.get("check_type"),
                    verification_scope=context.get("verification_scope"),
                )

                start_time = time.time()
                response = await client.get(url, test_context=api_context)
                api_duration = time.time() - start_time

                context["api_context"] = api_context

                if response.status_code != 200:
                    context["display_context"] = (
                        "Catalyst Center System Health -> Event Status"
                    )

                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"API Error: Failed to query system health events (HTTP {response.status_code})\n\n"
                            f"Failed to retrieve system health events from endpoint: {self.TEST_CONFIG['api_endpoint']}\n\n"
                            "Please verify:\n"
                            "• The Catalyst Center controller is reachable and responding\n"
                            "• Authentication credentials are valid\n"
                            "• The API endpoint is accessible\n"
                            "• Network connectivity to Catalyst Center is available"
                        ),
                        api_duration=api_duration,
                    )

                data = response.json()

                # Extract all health events using JMESPath
                health_events = jmespath.search("healthEvents[]", data) or []

                if not health_events:
                    context["display_context"] = (
                        "Catalyst Center System Health -> Event Status"
                    )

                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No system health events were discovered in Catalyst Center.\n\n"
                            "This may indicate that either:\n"
                            "• No events have occurred\n"
                            "• The API query returned no results\n"
                            "• The diagnostics subsystem is not reporting events\n\n"
                            "Please verify:\n"
                            "• The system health diagnostics feature is enabled\n"
                            "• Catalyst Center is operational and reporting events\n"
                            "• API endpoint is functioning as expected"
                        ),
                        api_duration=api_duration,
                    )

                expected_values = self.TEST_CONFIG["expected_values"]
                attributes_to_verify = expected_values.keys()

                all_events_non_critical = True
                validation_results = []
                failures = []
                non_critical_count = 0
                critical_count = 0

                for event in health_events:
                    event_failures = []
                    hostname = jmespath.search("hostname", event)
                    if hostname is None:
                        hostname = "Not Found"
                    elif hostname == "":
                        hostname = "<empty>"

                    instance = jmespath.search("instance", event)
                    if instance is None:
                        instance = "Not Found"
                    elif instance == "":
                        instance = "<empty>"

                    description = jmespath.search("description", event)
                    if description is None:
                        description = "Not Found"
                    elif description == "":
                        description = "<empty>"

                    # Check severity
                    severity = jmespath.search("severity", event)
                    if severity is None:
                        severity = "Not Found"
                    elif severity == "":
                        severity = "<empty>"

                    # Check state
                    state = jmespath.search("state", event)
                    if state is None:
                        state = "Not Found"
                    elif state == "":
                        state = "<empty>"

                    # Validation logic per pass/fail criteria
                    if str(severity) == "1":
                        event_failures.append(
                            f"  • severity: Expected not '1', got '{severity}'"
                        )
                    if str(state) == "Critical":
                        event_failures.append(
                            f"  • state: Expected not 'Critical', got '{state}'"
                        )

                    if event_failures:
                        all_events_non_critical = False
                        critical_count += 1
                        failure_detail = (
                            f"**Event:** Hostname='{hostname}', Instance='{instance}'\n"
                            f"  Description: {description}\n"
                            f"  Failures:\n" + "\n".join(event_failures)
                        )
                        failures.append(failure_detail)
                        validation_results.append(
                            f"❌ Hostname='{hostname}', Instance='{instance}' - severity={severity}, state={state}"
                        )
                    else:
                        non_critical_count += 1
                        validation_results.append(
                            f"✅ Hostname='{hostname}', Instance='{instance}' - severity={severity}, state={state}"
                        )

                context["total_events"] = len(health_events)
                context["non_critical_events"] = non_critical_count
                context["critical_events"] = critical_count

                result_summary = "\n".join(validation_results)

                if all_events_non_critical:
                    context["display_context"] = (
                        "Catalyst Center System Health -> Event Status"
                    )
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**Catalyst Center System Health Events Check PASSED**\n\n"
                            f"All {len(health_events)} reported system health events are non-critical.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**System Health Event Status:**\n"
                            f"• Total reported events: {len(health_events)}\n"
                            f"• Non-critical events: {non_critical_count}\n"
                            f"• All events non-critical: Yes\n"
                            f"• API query duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    context["display_context"] = (
                        "Catalyst Center System Health -> Event Status"
                    )
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**Catalyst Center System Health Events Check FAILED**\n\n"
                            f"One or more reported system health events are critical (severity=1 or state='Critical').\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Detailed Failures:**\n"
                            f"{chr(10).join(failures)}\n\n"
                            f"**System Health Event Status:**\n"
                            f"• Total reported events: {len(health_events)}\n"
                            f"• Non-critical events: {non_critical_count}\n"
                            f"• Critical events: {critical_count}\n\n"
                            f"**Please verify:**\n"
                            f"• Review critical events in Catalyst Center dashboard\n"
                            f"• Investigate root causes for events with severity=1 or state='Critical'\n"
                            f"• Ensure system health diagnostics are configured and operational\n"
                            f"• API query duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = f"Exception during system health event check: {str(e)}"
                self.logger.error(
                    f"Exception for Catalyst Center System Health Check: {error_msg}",
                    exc_info=True,
                )

                context["display_context"] = (
                    "Catalyst Center System Health -> Event Status"
                )

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
