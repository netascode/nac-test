# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Integration tests verifying downstream dependency compatibility.

nac-test declares several 3rd-party dependencies that are maintained primarily
for downstream consumer templates and test suites rather than being directly
used in nac_test core code.

This module verifies:
1. scrapli and scrapli-netconf driver imports and instantiation compatibility
   (Issue #965, used by nac-iosxe UtilsLib.py).
"""

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.windows,
]


def test_scrapli_and_scrapli_netconf_imports_and_instantiation() -> None:
    """Verify scrapli and scrapli-netconf driver imports and basic instantiation.

    Replicates the downstream consumer pattern from nac-iosxe UtilsLib.py:14.
    """
    import scrapli
    import scrapli_netconf
    from scrapli import AsyncDriver, Driver
    from scrapli_netconf import AsyncNetconfDriver, NetconfDriver

    assert scrapli_netconf.__version__
    assert hasattr(scrapli, "AsyncDriver"), "scrapli must export AsyncDriver"
    assert hasattr(scrapli, "Driver"), "scrapli must export Driver"
    assert issubclass(AsyncNetconfDriver, AsyncDriver)
    assert issubclass(NetconfDriver, Driver)

    # Verify AsyncNetconfDriver can be initialized with asyncssh transport
    async_conn = AsyncNetconfDriver(
        host="192.0.2.1",
        port=830,
        auth_username="admin",
        auth_password="password",
        auth_strict_key=False,
        transport="asyncssh",
        strip_namespaces=True,
    )
    assert async_conn.host == "192.0.2.1"
    assert async_conn.port == 830
    assert async_conn.transport_name == "asyncssh"

    # Verify sync NetconfDriver can be initialized with system transport
    sync_conn = NetconfDriver(
        host="192.0.2.1",
        port=830,
        auth_username="admin",
        auth_password="password",
        auth_strict_key=False,
        transport="system",
        strip_namespaces=True,
    )
    assert sync_conn.host == "192.0.2.1"
    assert sync_conn.port == 830
    assert sync_conn.transport_name == "system"
