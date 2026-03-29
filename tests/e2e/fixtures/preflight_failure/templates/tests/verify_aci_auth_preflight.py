# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
# UTF-8: Ü ö ä 日本語 中文

"""
[NRFU]: Pre-flight failure e2e scenario stub
--------------------------------------------
Minimal PyATS test stub used by the pre-flight auth failure e2e scenario.
This file exists solely to trigger ACI controller detection and the pre-flight
auth check. It is never executed — the pre-flight failure causes PyATS to be
skipped before any tests run.
"""

from nac_test_pyats_common.aci.test_base import APICTestBase
from pyats import aetest

TITLE = "Pre-flight failure stub"


class VerifyAciAuthPreflight(APICTestBase):
    @aetest.test
    def verify_placeholder(self) -> None:
        """Placeholder test — never executed in the pre-flight failure scenario."""
        pass
