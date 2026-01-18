# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
simple test
"""

import logging
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

    # TEST_CONFIG follows the standard pattern used by APIC tests
    TEST_CONFIG = {
        "resource_type": "Truth Assertion",
        "test_type_name": "Truth Verification",
        "identifier_format": "Truth Test {test_id}",
        "step_name_format": "Verify Truth: {expected_state}",
    }

    @aetest.test
    def test_true(self, steps):
        """Main test using standard base class pattern with steps for detailed reporting."""
        # Generate results using format_verification_result()
        results = [self._verify_single_truth()]

        # Use base class smart result processing
        self.process_results_smart(results, steps)

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

    def _verify_single_truth(self) -> Dict[str, Any]:
        """
        Verifies that True is indeed True. Returns a standardized result dict.

        Uses the base class format_verification_result() method to ensure
        proper integration with the reporter.
        """
        # Build context object with all verification metadata
        context = {
            "test_id": "truth_test_001",
            "expected_state": "True",
            "test_description": "Verify that True is indeed True",
        }

        print("Verifying that True is indeed True...")

        try:
            assert 1 == 1, "test error"

            # Use base class formatter for standardized result structure
            self.passed()
            return self.format_verification_result(
                status=ResultStatus.PASSED,
                context=context,
                reason="Truth has been verified successfully",
                api_duration=0.0,
            )

        except Exception as e:
            # Use base class formatter for failed results too
            self.failed()

            return self.format_verification_result(
                status=ResultStatus.FAILED,
                context=context,
                reason=f"Truth verification failed: {e}",
                api_duration=0.0,
            )
