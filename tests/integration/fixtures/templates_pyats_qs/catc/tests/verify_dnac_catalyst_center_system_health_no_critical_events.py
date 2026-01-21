# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify Catalyst Center System Health - No Critical Events
-----------------------------------------------------------------
This job file verifies that Cisco Catalyst Center has no system health events
in a Critical state, ensuring the controller is operating without major faults.
"""

import time
from pyats import aetest

import jmespath
from nac_test_pyats_common.catc import CatalystCenterTestBase
from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify Catalyst Center System Health Has No Critical Events"

DESCRIPTION = """This test validates the overall health of Cisco Catalyst Center by checking
for the absence of critical system health events. System health events reflect underlying
controller platform issues, service faults, or infrastructure problems. Ensuring no events
are in a Critical state is essential for stable controller operations, reliable network
automation, and uninterrupted service delivery to managed devices."""

SETUP = (
    "* Access to an active Cisco Catalyst Center controller via HTTPS API is available.\n"
    "* Authentication credentials for Catalyst Center are valid and configured.\n"
    "* System diagnostics are enabled and Catalyst Center services are operational.\n"
)

PROCEDURE = (
    "* Establish HTTPS connection to the Catalyst Center controller.\n"
    "* Query the API endpoint: */dna/intent/api/v1/diagnostics/system/health?summary=true*.\n"
    "* Parse the JSON response and extract the `healthEvents` array.\n"
    "* For EACH health event:\n"
    "    * Extract the `severity` and `state` attributes.\n"
    "    * Verify that `severity` is NOT equal to 1 (Critical).\n"
    "    * Verify that `state` is NOT equal to 'Critical'.\n"
)

PASS_FAIL_CRITERIA = (
    "**This test passes when all of the following conditions are met:**\n"
    "\n"
    "* At least one system health event is returned by the Catalyst Center API.\n"
    "* ALL system health events have `severity` not equal to 1 and `state` not equal to 'Critical'.\n"
    "\n"
    "**This test fails if any of the following criteria are met:**\n"
    "\n"
    "* No system health events are found in the API response.\n"
    "* ANY event has `severity` equal to 1 (Critical).\n"
    "* ANY event has `state` equal to 'Critical'.\n"
    "* The API query fails or returns an error response.\n"
)



class VerifyCatCSystemHealthNoCriticalEvents(CatalystCenterTestBase):
    """
    [DNAC NRFU] Verify Catalyst Center System Health - No Critical Events

    Verifies that there are no system health events with severity=1 (Critical)
    or state="Critical" in Catalyst Center, indicating system is free of critical faults.
    """

    TEST_CONFIG = {
        "resource_type": "Catalyst Center System Health Events",
        "api_endpoint": "/dna/intent/api/v1/diagnostics/system/health?summary=true",
        "expected_values": {
            "severity": "not 1",
            "state": "not Critical",
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_health_events",
            "healthy_events",
            "critical_events",
        ],
    }

    @aetest.test
    def test_system_health_no_critical_events(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """
        Returns a single context to trigger the global system health events check.
        """
        return [
            {
                "check_type": "system_health_no_critical_events",
                "verification_scope": "all_health_events",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification: Discover ALL system health events and verify none are Critical.
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
                    self.TEST_CONFIG['resource_type'],
                    "Global System Health Check",
                    check_type=context.get("check_type"),
                    verification_scope=context.get("verification_scope"),
                )

                start_time = time.time()
                response = await client.get(url, test_context=api_context)
                api_duration = time.time() - start_time

                context["api_context"] = api_context

                if response.status_code != 200:
                    context["display_context"] = "Catalyst Center System Health -> Events"

                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"API Error: Failed to query system health events (HTTP {response.status_code})\n\n"
                            f"Failed to retrieve health events from endpoint: {self.TEST_CONFIG['api_endpoint']}\n\n"
                            "Please verify:\n"
                            "• The Catalyst Center controller is reachable and responding\n"
                            "• Authentication credentials are valid\n"
                            "• The API endpoint is accessible\n"
                            "• Network connectivity to Catalyst Center is available"
                        ),
                        api_duration=api_duration,
                    )

                data = response.json()

                health_events = jmespath.search("healthEvents[]", data) or []

                if not health_events:
                    context["display_context"] = "Catalyst Center System Health -> Events"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No system health events found in Catalyst Center response.\n\n"
                            "This indicates that either:\n"
                            "• No health events have been generated\n"
                            "• The API query returned no results\n"
                            "• System diagnostics may not be enabled\n\n"
                            "Please verify:\n"
                            "• Catalyst Center system diagnostics are operational\n"
                            "• API endpoint is returning valid data"
                        ),
                        api_duration=api_duration,
                    )

                expected_values = self.TEST_CONFIG["expected_values"]
                attributes_to_verify = expected_values.keys()

                all_events_healthy = True
                validation_results = []
                failures = []
                healthy_count = 0
                critical_count = 0

                for idx, event in enumerate(health_events):
                    hostname = jmespath.search("hostname", event) or "Not Found"
                    description = jmespath.search("description", event) or "No Description"
                    severity = jmespath.search("severity", event) or "Not Found"
                    state = jmespath.search("state", event) or "Not Found"
                    timestamp = jmespath.search("timestamp", event) or "Not Found"
                    status = jmespath.search("status", event) or "Not Found"
                    instance = jmespath.search("instance", event) or "Not Found"
                    subDomain = jmespath.search("subDomain", event) or "Not Found"
                    domain = jmespath.search("domain", event) or "Not Found"

                    event_failures = []

                    # Check severity
                    if str(severity) == "1":
                        event_failures.append(
                            f"  • severity: Expected not '1', got '{severity}'"
                        )
                    # Check state
                    if str(state) == "Critical":
                        event_failures.append(
                            f"  • state: Expected not 'Critical', got '{state}'"
                        )

                    if event_failures:
                        all_events_healthy = False
                        critical_count += 1
                        failure_detail = (
                            f"**Event #{idx+1} ({instance})**\n"
                            f"  Hostname: {hostname}\n"
                            f"  Domain/SubDomain: {domain}/{subDomain}\n"
                            f"  Description: {description}\n"
                            f"  Severity: {severity}\n"
                            f"  State: {state}\n"
                            f"  Status: {status}\n"
                            f"  Timestamp: {timestamp}\n"
                            f"  Failures:\n" + "\n".join(event_failures)
                        )
                        failures.append(failure_detail)
                        validation_results.append(
                            f"❌ Event '{instance}' on {hostname} - severity={severity}, state={state}, status={status}"
                        )
                    else:
                        healthy_count += 1
                        validation_results.append(
                            f"✅ Event '{instance}' on {hostname} - severity={severity}, state={state}, status={status}"
                        )

                context["total_health_events"] = len(health_events)
                context["healthy_events"] = healthy_count
                context["critical_events"] = critical_count

                result_summary = "\n".join(validation_results)

                context["display_context"] = "Catalyst Center System Health -> Events"

                if all_events_healthy:
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**Catalyst Center System Health Events Check PASSED**\n\n"
                            f"All {len(health_events)} system health events have severity ≠ 1 (Critical) and state ≠ 'Critical'.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**System Health Events Status:**\n"
                            f"• Total discovered health events: {len(health_events)}\n"
                            f"• Events without Critical severity/state: {healthy_count}\n"
                            f"• All events healthy (no Critical): Yes\n"
                            f"• API query duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**Catalyst Center System Health Events Check FAILED**\n\n"
                            f"One or more system health events have severity=1 (Critical) or state='Critical'.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Detailed Failures:**\n"
                            f"{chr(10).join(failures)}\n\n"
                            f"**System Health Events Status:**\n"
                            f"• Total discovered health events: {len(health_events)}\n"
                            f"• Events without Critical severity/state: {healthy_count}\n"
                            f"• Events with Critical severity/state: {critical_count}\n\n"
                            f"**Please verify:**\n"
                            f"• Review system health events in Catalyst Center\n"
                            f"• Investigate any events with severity=1 or state='Critical'\n"
                            f"• Address underlying system issues or faults\n"
                            f"• Ensure Catalyst Center services are healthy\n"
                            f"• API query duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = f"Exception during system health events check: {str(e)}"
                self.logger.error(
                    f"Exception for Catalyst Center System Health Events Check: {error_msg}",
                    exc_info=True,
                )

                context["display_context"] = "Catalyst Center System Health -> Events"

                reason = (
                    f"PyATS Framework Exception: {error_msg}\n\n"
                    f"This is a PyATS code issue, not an issue with your data model, "
                    f"Catalyst Center configuration, or your network.\n\n"
                    f"Please contact Cisco TAC for support with this error."
                )

                return self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason=reason,
                    api_duration=0,
                )