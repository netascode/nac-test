# -*- coding: utf-8 -*-

"""APIC-specific authentication implementation."""

import httpx
from nac_test.pyats_core.common.auth_cache import AuthCache


class APICAuth:
    """APIC-specific authentication implementation"""

    @staticmethod
    def authenticate(url: str, username: str, password: str) -> tuple[str, int]:
        """Perform APIC authentication

        Args:
            url: APIC URL
            username: APIC username
            password: APIC password

        Returns:
            Tuple of (token, expires_in_seconds)
        """
        with httpx.Client(verify=False) as client:
            response = client.post(
                f"{url}/api/aaaLogin.json",
                json={"aaaUser": {"attributes": {"name": username, "pwd": password}}},
            )
            response.raise_for_status()

            token = response.json()["imdata"][0]["aaaLogin"]["attributes"]["token"]
            # APIC tokens typically last 600 seconds
            return token, 600

    @classmethod
    def get_token(cls, url: str, username: str, password: str) -> str:
        """Get APIC token using generic cache

        Args:
            url: APIC URL
            username: APIC username
            password: APIC password

        Returns:
            APIC authentication token
        """
        return AuthCache.get_or_create_token(
            controller_type="ACI",
            url=url,
            username=username,
            password=password,
            auth_func=cls.authenticate,
        )
