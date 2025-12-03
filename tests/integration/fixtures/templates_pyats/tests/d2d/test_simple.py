"""
simple test
"""

import logging
import asyncio
from typing import Dict, List, Any

from pyats import aetest

from nac_test.pyats_core.reporting.types import ResultStatus
from nac_test.pyats_core.common.ssh_base_test import SSHTestBase

logger = logging.getLogger(__name__)

TITLE = "Verify that True is indeed True"

DESCRIPTION = "The purpose of this test case is to exist and succeed."

SETUP = "* Setup steps"

PROCEDURE = "* Test Procedure.\n"

PASS_FAIL_CRITERIA = "If this test ever failed, hell might has well freeze over"


class VerifyTruth(SSHTestBase):
    """Verifies BGP peer status on SD-WAN cEdge devices."""

    def __init__(self, *args, **kwargs):
        """Initialize the test case and its attributes."""
        super().__init__(*args, **kwargs)

    @aetest.test
    async def test_true(self, steps):
        """Main test using async pattern with steps for detailed reporting."""
        tasks = [self._verify_single_truth_async()]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        self._process_results_with_steps(results)

    def get_ssh_device_inventory(self) -> List[Dict[str, Any]]:
        return [
            {
                "hostname": "mock_iosxe",
                "os": "iosxe",
                "username": "cisco",
                "password": "cisco",
                "command": "tests/integration/mocks/mock_unicon.py --hostname mock_iosxe iosxe",
            }
        ]

    async def _verify_single_truth_async(
        self,
    ) -> Dict[str, Any]:
        """
        Verifies a single neighbor+address-family combination. Returns a detailed result dict.
        """
        verification = {
            "expected_state": "True",
        }
        print("Verifying that True is indeed True...")
        try:
            # assert False, 'test error'
            return self._result_dict(
                "PASSED",
                "Truth has been verified",
                verification,
            )

        except Exception as e:
            return self._result_dict(
                "FAILED",
                f"failure: {e}",
                verification,
            )

    def _result_dict(
        self,
        status,
        reason,
        verification,
    ):
        """
        Helper to build a structured result dictionary for each neighbor+AF verification.
        """
        return {
            "status": status,
            "reason": reason,
            "verification": verification,
        }

    def _process_results_with_steps(self, results: List[Dict[str, Any]], steps):
        """
        Process results with detailed step reporting and HTML report collection.
        Groups results by template for hierarchical reporting, logs details, and sets step results.
        """
        if not results:
            self.passed("No BGP neighbors were found to verify.")
            return
        # -----------------------------
        # Log summary statistics
        # -----------------------------
        passed = [r for r in results if r["status"] == "PASSED"]
        failed = [r for r in results if r["status"] == "FAILED"]
        skipped = [r for r in results if r["status"] == "SKIPPED"]
        logger.info(
            f"Truth verification: {len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped"
        )
        for result in results:
            logger.debug(f"Verification result: {result}")
        with steps.start("Verify Truth", continue_=True) as step:
            step_name = "test step name"
            if result["status"] == "PASSED":
                step.passed(result["reason"])
                self.result_collector.add_result(
                    ResultStatus.PASSED,
                    f"{step_name} - {result['reason']}",
                )
                self.passed()
            elif result["status"] == "SKIPPED":
                step.skipped(result["reason"])
                self.result_collector.add_result(
                    ResultStatus.SKIPPED,
                    f"{step_name} - {result['reason']}",
                )
                self.skipped()
            else:
                step.failed(result["reason"])
                self.result_collector.add_result(
                    ResultStatus.FAILED,
                    f"{step_name} - {result['reason']}",
                )
                self.failed()
