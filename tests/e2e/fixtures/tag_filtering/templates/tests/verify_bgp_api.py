# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import time

from nac_test_pyats_common.aci.test_base import APICTestBase
from pyats import aetest

from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify BGP API Test"
DESCRIPTION = "Simple BGP verification test via API for tag filtering e2e tests."
SETUP = "* Access to APIC controller is available.\n"
PROCEDURE = "* Query APIC API and verify response.\n"
PASS_FAIL_CRITERIA = "* API returns successful response.\n"


class VerifyBgpApi(APICTestBase):
    groups = ["bgp"]

    TEST_CONFIG = {
        "resource_type": "BGP API Test",
        "api_endpoint": "node/class/infraWiNode.json",
        "expected_values": {},
        "log_fields": ["check_type"],
    }

    @aetest.test
    def test_bgp_api(self, steps):
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        return [{"check_type": "bgp_api_check"}]

    async def verify_item(self, semaphore, client, context):
        async with semaphore:
            url = f"/api/{self.TEST_CONFIG['api_endpoint']}"
            api_context = self.build_api_context(
                self.TEST_CONFIG["resource_type"],
                "BGP API",
                check_type=context.get("check_type"),
            )
            start_time = time.time()
            response = await client.get(url, test_context=api_context)
            api_duration = time.time() - start_time
            context["api_context"] = api_context
            context["display_context"] = "BGP API Test"

            if response.status_code == 200:
                return self.format_verification_result(
                    status=ResultStatus.PASSED,
                    context=context,
                    reason="BGP API check passed.",
                    api_duration=api_duration,
                )
            return self.format_verification_result(
                status=ResultStatus.FAILED,
                context=context,
                reason=f"API Error: HTTP {response.status_code}",
                api_duration=api_duration,
            )
