# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Contract: auth adapters normalize trailing slashes in controller URLs.

Verifies that authentication endpoints constructed by pyats-common adapters
never contain double-slashes, regardless of whether the user sets a trailing /
on the controller URL env var.

The httpserver expects clean paths (e.g. /api/aaaLogin.json). If an adapter
fails to strip the trailing slash, it would request //api/aaaLogin.json which
won't match the handler — causing an auth failure and a test assertion error.
"""

import pytest
from pytest_httpserver import HTTPServer

from nac_test.core.controller_auth import (
    AuthOutcome,
    preflight_auth_check,
)
from nac_test.core.types import ControllerContext

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("url_suffix", ["", "/"], ids=["clean", "trailing_slash"])
def test_aci_preflight_normalizes_url(
    httpserver: HTTPServer,
    monkeypatch: pytest.MonkeyPatch,
    url_suffix: str,
) -> None:
    """APIC auth succeeds regardless of trailing slash on ACI_URL."""
    httpserver.expect_request("/api/aaaLogin.json", method="POST").respond_with_json(
        {
            "imdata": [
                {
                    "aaaLogin": {
                        "attributes": {
                            "token": "test-token",
                            "refreshTimeoutSeconds": "600",
                        }
                    }
                }
            ]
        },
        status=200,
    )

    monkeypatch.setenv("ACI_URL", httpserver.url_for("") + url_suffix)
    monkeypatch.setenv("ACI_USERNAME", "admin")
    monkeypatch.setenv("ACI_PASSWORD", "password")

    ctx = ControllerContext(controller_type="ACI", auth_method="session")
    result = preflight_auth_check(ctx)

    assert result.success is True, (
        f"Auth failed with url_suffix={url_suffix!r}: {result.detail}"
    )
    assert result.reason == AuthOutcome.SUCCESS


@pytest.mark.parametrize("url_suffix", ["", "/"], ids=["clean", "trailing_slash"])
def test_sdwan_preflight_normalizes_url(
    httpserver: HTTPServer,
    monkeypatch: pytest.MonkeyPatch,
    url_suffix: str,
) -> None:
    """SDWAN session auth succeeds regardless of trailing slash on SDWAN_URL."""
    httpserver.expect_request("/j_security_check", method="POST").respond_with_data(
        "",
        status=200,
        headers={"Set-Cookie": "JSESSIONID=test-session; Path=/"},
    )
    httpserver.expect_request(
        "/dataservice/client/token", method="GET"
    ).respond_with_data(
        "test-xsrf-token",
        status=200,
    )

    monkeypatch.setenv("SDWAN_URL", httpserver.url_for("") + url_suffix)
    monkeypatch.setenv("SDWAN_USERNAME", "admin")
    monkeypatch.setenv("SDWAN_PASSWORD", "password")

    ctx = ControllerContext(controller_type="SDWAN", auth_method="session")
    result = preflight_auth_check(ctx)

    assert result.success is True, (
        f"Auth failed with url_suffix={url_suffix!r}: {result.detail}"
    )
    assert result.reason == AuthOutcome.SUCCESS
