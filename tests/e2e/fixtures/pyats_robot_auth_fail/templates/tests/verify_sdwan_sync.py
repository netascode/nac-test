# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
# Minimal PyATS test for discovery - never executes (pre-flight auth fails)
from nac_test_pyats_common.sdwan import SDWANManagerTestBase
from pyats import aetest


class Test(SDWANManagerTestBase):
    @aetest.test
    def test(self):
        pass
