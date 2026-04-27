# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import jmespath
from nac_test_pyats_common.aci.test_base import APICTestBase
from pyats import aetest

from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify APIC Status"
DESCRIPTION = "Verify APIC controllers are available."
SETUP = "APIC access configured."
PROCEDURE = "Query infraWiNode and verify operSt=available."
PASS_FAIL_CRITERIA = "All APICs must have operSt=available."


class VerifyApicApplianceOperationalStatus(APICTestBase):
    TEST_CONFIG = {
        "resource_type": "APIC Status",
        "api_endpoint": 'node/class/infraWiNode.json?query-target-filter=wcard(infraWiNode.dn,"topology/pod-1/node-1/")',
        "expected_values": {"operSt": "available"},
        "log_fields": ["total_items", "healthy_items", "unhealthy_items"],
    }

    @aetest.test
    def test_apic_appliance_oper_status(self, steps):
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        return [{"check_type": "apic_status"}]

    async def verify_item(self, semaphore, client, context):
        async with semaphore:
            try:
                url = f"/api/{self.TEST_CONFIG['api_endpoint']}"
                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"], "All APICs"
                )
                response = await client.get(url, test_context=api_context)
                context["api_context"] = api_context

                if response.status_code != 200:
                    context["display_context"] = "APIC Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=f"API error: HTTP {response.status_code}",
                    )

                data = response.json()
                appliances = (
                    jmespath.search("imdata[].infraWiNode.attributes", data) or []
                )

                if not appliances:
                    context["display_context"] = "APIC Status"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason="No APICs discovered",
                    )

                healthy = sum(1 for a in appliances if a.get("operSt") == "available")
                unhealthy = len(appliances) - healthy

                context["total_items"] = len(appliances)
                context["healthy_items"] = healthy
                context["unhealthy_items"] = unhealthy
                context["display_context"] = "APIC Status"

                if unhealthy == 0:
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=f"All {healthy} APICs available",
                    )
                else:
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=f"{unhealthy}/{len(appliances)} APICs unavailable",
                    )

            except Exception as e:
                context["display_context"] = "APIC Status"
                return self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason=f"Exception: {e}",
                )
