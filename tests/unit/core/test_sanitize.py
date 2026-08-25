# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for output sanitization (issue #881)."""

import pytest

from nac_test.pyats_core.reporting.sanitize import sanitize_output

_R = "<REDACTED>"


# ── CLI rules ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("username admin password 7 08354D4D1B48", f"username admin password 7 {_R}"),
        ("enable secret 5 $1$abc$XYZ123", f"enable secret 5 {_R}"),
        ("password 0 MyPlaintext!", f"password 0 {_R}"),
        ("key-string 7 01234567890ABCDEF", f"key-string 7 {_R}"),
        ("server-key 7 0123456789ABCDEF", f"server-key 7 {_R}"),
        ("pac key 6 FLgBaJHXja070ALlMQ", f"pac key 6 {_R}"),
        ("domain-password S3cr3t", f"domain-password {_R}"),
        ("snmp-server community PUBLIC RO", f"snmp-server community {_R} RO"),
        (
            "snmp-server host 10.0.0.1 version 3 priv AUTHPASS",
            f"snmp-server host 10.0.0.1 version 3 priv {_R}",
        ),
        ("set-key ascii 0 MyPSK123", f"set-key ascii 0 {_R}"),
        ("set-key hex SecretHex", f"set-key hex {_R}"),
        ("attribute type password 0A1B2C3D", f"attribute type password {_R}"),
    ],
    ids=[
        "password-type7",
        "secret-type5",
        "password-type0-cleartext",
        "key-string",
        "server-key",
        "pac-key",
        "domain-password",
        "snmp-community",
        "snmp-host-priv",
        "wlan-psk-ascii",
        "wlan-psk-hex",
        "aaa-attribute-password",
    ],
)
def test_cli_secrets(raw: str, expected: str) -> None:
    assert sanitize_output(raw) == expected


# ── JSON API rules ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"password": "cisco123"}', f'{{"password": "{_R}"}}'),
        ('{"sharedSecret": "T@c@cs!"}', f'{{"sharedSecret": "{_R}"}}'),
        ('{"community": "public"}', f'{{"community": "{_R}"}}'),
        ('{"presharedKey": "vpnkey123"}', f'{{"presharedKey": "{_R}"}}'),
        ('{"snmpAuthPassword": "authpass"}', f'{{"snmpAuthPassword": "{_R}"}}'),
        ('{"enableSecret": "en@ble!"}', f'{{"enableSecret": "{_R}"}}'),
        ('{"Password": "foo"}', f'{{"Password": "{_R}"}}'),
    ],
    ids=[
        "password",
        "sharedSecret",
        "community",
        "presharedKey",
        "snmpAuthPassword",
        "enableSecret",
        "Password-capitalized",
    ],
)
def test_json_secrets(raw: str, expected: str) -> None:
    assert sanitize_output(raw) == expected


def test_json_non_secret_field_unchanged() -> None:
    """JSON with no secret-like keys passes through."""
    raw = '{"status": "SUCCESS", "hostname": "switch-01"}'
    assert sanitize_output(raw) == raw


# ── Heuristic dispatch ──────────────────────────────────────────────────────


def test_cli_rules_not_applied_to_json() -> None:
    """CLI patterns inside a JSON body must not trigger CLI rules."""
    raw = '{"command": "enable secret 5 $1$abc$XYZ123"}'
    assert sanitize_output(raw) == raw


def test_json_rules_not_applied_to_cli() -> None:
    """JSON-like key names in CLI output must not trigger JSON rules."""
    raw = 'description "community center"'
    assert sanitize_output(raw) == raw


# ── Non-sensitive passthrough ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [
        "interface GigabitEthernet0/0",
        "ip address 10.0.0.1 255.255.255.0",
        "",
    ],
    ids=["interface", "ip-address", "empty"],
)
def test_non_sensitive_unchanged(raw: str) -> None:
    assert sanitize_output(raw) == raw


# ── Integration: multi-line config block ────────────────────────────────────


def test_full_config_block() -> None:
    config = (
        "hostname CORE-SW1\n"
        "!\n"
        "enable secret 5 $1$xyz$HASH\n"
        "!\n"
        "username admin password 7 045802150C2E\n"
        "!\n"
        "snmp-server community PRIVATE RW\n"
        "snmp-server community PUBLIC RO\n"
        "snmp-server host 10.1.1.1 version 3 priv AuthKey\n"
        "!\n"
        "interface Vlan100\n"
        " ip address 10.100.0.1 255.255.255.0\n"
    )
    secrets = {"HASH", "045802150C2E", "PRIVATE", "PUBLIC", "AuthKey"}
    result = sanitize_output(config)

    # Secrets redacted
    for secret in secrets:
        assert secret not in result
    assert result.count(_R) == len(secrets)

    # Non-sensitive preserved
    assert "hostname CORE-SW1" in result
    assert "interface Vlan100" in result
    assert "10.1.1.1" in result
