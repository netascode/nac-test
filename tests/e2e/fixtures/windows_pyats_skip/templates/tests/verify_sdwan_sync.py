# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Minimal PyATS test for Windows skip scenario."""

from nac_test_pyats_common.sdwan import SDWANManagerTestBase
from pyats import aetest


class VerifySDWANSync(SDWANManagerTestBase):
    """Minimal SD-WAN test to verify PyATS discovery on Windows."""

    @aetest.test
    def test_sync(self):
        pass
