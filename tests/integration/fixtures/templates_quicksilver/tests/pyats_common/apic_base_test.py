# -*- coding: utf-8 -*-

"""APIC-specific base test class."""

import asyncio
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase
from .apic_auth import APICAuth


class APICTestBase(NACTestBase):
    """Base class for APIC API tests with enhanced reporting.

    This class extends the generic NACTestBase to provide APIC-specific
    functionality including:
    - APIC authentication token management
    - API call tracking for HTML reports
    - Wrapped HTTP client for automatic response capture
    """

    @aetest.setup
    def setup(self):
        """Setup method that extends the generic base class setup"""
        super().setup()

        # Get shared APIC token using file-based locking
        self.token = APICAuth.get_token(
            self.controller_url, self.username, self.password
        )

        # Store the APIC client for use in verification methods
        self.client = self.get_apic_client()

    def get_apic_client(self):
        """Get an httpx async client configured for APIC with response tracking.

        Returns:
            httpx.AsyncClient configured with APIC authentication, base URL,
            and wrapped for automatic API call tracking
        """
        headers = {"Cookie": f"APIC-cookie={self.token}"}
        client = self.pool.get_client(
            base_url=self.controller_url, headers=headers, verify=False
        )

        # Use the generic tracking wrapper from base class
        return self.wrap_client_for_tracking(client, device_name="APIC")

    def run_async_verification_test(self, steps):
        """
        Simple entry point that uses base class orchestration.

        This thin wrapper:
        1. Calls NACTestBase.run_verification_async()
        2. Passes results to NACTestBase.process_results_smart()

        The actual verification logic is handled by:
        - get_items_to_verify() - implemented by the test class
        - verify_item() - implemented by the test class

        Args:
            steps: PyATS steps object for test reporting
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Call the base class generic orchestration
            results = loop.run_until_complete(self.run_verification_async())

            # Process results using smart configuration-driven processing
            self.process_results_smart(results, steps)
        finally:
            # Clean up the APIC client connection
            if hasattr(self, "client"):
                loop.run_until_complete(self.client.aclose())
            loop.close()
