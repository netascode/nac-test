# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify SD-WAN Controllers (FAILURE TEST)
-------------------------------------------------
This test is designed to fail for integration testing purposes.
It queries a different API endpoint with incompatible data structure.
"""

import time

import jmespath
from nac_test_pyats_common.sdwan import SDWANManagerTestBase
from pyats import aetest

from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify SD-WAN Controllers (Failure Test)"

DESCRIPTION = """This test is designed to fail for integration testing.
It queries a different API endpoint expecting vedges data structure."""

SETUP = "* This is a test designed to fail.\n"

PROCEDURE = (
    "* Query different API endpoint.\n"
    "* Validation fails due to incompatible data structure.\n"
)

PASS_FAIL_CRITERIA = "**This test is designed to fail.**\n"


class VerifySDWANControllers(SDWANManagerTestBase):
    """
    [SDWAN-Manager] Test designed to fail - uses incompatible endpoint
    """

    TEST_CONFIG = {
        "resource_type": "SDWAN Controllers",
        "api_endpoint": "/dataservice/system/device/controllers",  # Different endpoint
        "expected_values": {
            "configStatusMessage": "In Sync",  # Field doesn't exist in controllers
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_controllers",
        ],
    }

    @aetest.test
    def test_controller_sync(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """Returns a single context to trigger check."""
        return [
            {
                "check_type": "controller_config_sync",
                "verification_scope": "all_controllers",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification: Query controllers endpoint expecting vedges data structure.
        Will fail because controllers don't have configStatusMessage field.
        """
        async with semaphore:
            try:
                url = self.TEST_CONFIG["api_endpoint"]
                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"],
                    "SDWAN Controllers",
                    check_type=context.get("check_type"),
                    verification_scope=context.get("verification_scope"),
                )

                start_time = time.time()
                response = await client.get(url, test_context=api_context)
                api_duration = time.time() - start_time

                context["api_context"] = api_context

                if response.status_code != 200:
                    context["display_context"] = "SDWAN Controllers"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=f"API Error: HTTP {response.status_code}",
                        api_duration=api_duration,
                    )

                data = response.json()

                # Try to find items (controllers have different structure than vedges)
                items_to_check = jmespath.search("data", data) or []

                if not items_to_check:
                    context["display_context"] = "SDWAN Controllers"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No controllers discovered (or incompatible data structure).\n\n"
                            "This test is designed to fail for integration testing."
                        ),
                        api_duration=api_duration,
                    )

                # Check for expected field (won't exist in controllers)
                expected_values = self.TEST_CONFIG["expected_values"]
                failures = []

                for item in items_to_check:
                    device_id = jmespath.search("deviceIP", item) or "Unknown"
                    config_status = jmespath.search("configStatusMessage", item)

                    if config_status is None:
                        failures.append(
                            f"Controller '{device_id}': Missing 'configStatusMessage' field "
                            f"(expected field not present in controllers data structure)"
                        )

                if failures or not items_to_check:
                    context["display_context"] = "SDWAN Controllers"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "Controller sync check failed (incompatible data structure).\n\n"
                            + "\n".join(failures)
                            + "\n\n"
                            "This test is designed to fail for integration testing."
                        ),
                        api_duration=api_duration,
                    )

                # Shouldn't reach here, but fail anyway
                context["display_context"] = "SDWAN Controllers"
                return self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason="Test designed to fail",
                    api_duration=api_duration,
                )

            except Exception as e:
                error_msg = f"Exception during controller check: {str(e)}"
                context["display_context"] = "SDWAN Controllers"
                return self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason=error_msg,
                    api_duration=0,
                )
