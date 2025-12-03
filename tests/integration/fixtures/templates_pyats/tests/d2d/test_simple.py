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
    """Verifies that True is indeed True (simple test for HTML report generation)."""

    # Required class variable for base test reporting
    TEST_TYPE_NAME = "Truth Verification"

    def __init__(self, *args, **kwargs):
        """Initialize the test case and its attributes."""
        super().__init__(*args, **kwargs)

    @aetest.test
    async def test_true(self, steps):
        """Main test using async pattern with steps for detailed reporting."""
        tasks = [self._verify_single_truth_async()]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        self._process_results_with_steps(results, steps)

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
            self.passed("No verifications to process.")
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

        # Process each result with proper step creation
        for result in results:
            logger.debug(f"Verification result: {result}")

            # Extract verification details
            verification = result.get("verification", {})
            expected_state = verification.get("expected_state", "True")

            with steps.start(f"Verify Truth: {expected_state}", continue_=True) as step:
                step_name = "Truth Verification"

                if result["status"] == "PASSED":
                    step.passed(result["reason"])
                    self.result_collector.add_result(
                        ResultStatus.PASSED,
                        f"{step_name} - {result['reason']}",
                    )
                elif result["status"] == "SKIPPED":
                    step.skipped(result["reason"])
                    self.result_collector.add_result(
                        ResultStatus.SKIPPED,
                        f"{step_name} - {result['reason']}",
                    )
                else:
                    step.failed(result["reason"])
                    self.result_collector.add_result(
                        ResultStatus.FAILED,
                        f"{step_name} - {result['reason']}",
                    )

        # Determine overall test result after processing all verifications
        if failed:
            self.failed(f"Truth verification failed: {len(failed)} failure(s)")
        elif skipped and not passed:
            self.skipped("All verifications were skipped")
        else:
            self.passed(f"Truth verification passed: {len(passed)} verification(s)")
