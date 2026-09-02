# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Sanitize command and API output to redact secrets before HTML report persistence.

Applies regex-based redaction rules to prevent credentials, community strings,
pre-shared keys, and similar sensitive data from leaking into HTML report
artifacts. Called from :meth:`TestResultCollector.add_command_api_execution`
as the single chokepoint before any output reaches disk.

CLI and JSON rules are kept separate and applied based on a content heuristic:
output starting with ``{`` or ``[`` is treated as JSON, everything else as CLI.

See: https://github.com/netascode/nac-test/issues/881
"""

import re

_REDACTED = "<REDACTED>"

# ── CLI rules (IOS / IOS-XE / NX-OS / IOS-XR style) ────────────────────────
# Compiled once at import time — order matters for overlapping patterns.
_CLI_RULES: list[tuple[re.Pattern[str], str]] = [
    # Typed secrets / passwords / keys (covers types 0-9 and beyond):
    #   secret <N> <hash>, password <N> <hash>,
    #   key <N> <hex>, key-string <N> <val>,
    #   server-key <N> <hex>, pac key <N> <hex>
    (
        re.compile(
            r"\b((?:server-|pac\s+)?key(?:-string)?|password|secret)"
            r"\s+(\d+)\s+\S+"
        ),
        r"\1 \2 " + _REDACTED,
    ),
    # IS-IS / OSPF domain-password
    (re.compile(r"\b(domain-password)\s+\S+"), r"\1 " + _REDACTED),
    # SNMP community string
    (re.compile(r"\b(snmp-server\s+community)\s+(\S+)"), r"\1 " + _REDACTED),
    # SNMP host privacy password (value after 'priv' keyword)
    (re.compile(r"\b(snmp-server\s+host\s+.*\s+priv)\s+\S+"), r"\1 " + _REDACTED),
    # WLAN WPA PSK set-key (ascii or hex, with optional type 0 prefix)
    (re.compile(r"(set-key\s+(?:ascii|hex)\s+(?:0\s+)?)\S+"), r"\1" + _REDACTED),
    # AAA attribute type password (hex hash used in RADIUS/TACACS)
    (re.compile(r"(attribute\s+type\s+password\s+)\S+"), r"\1" + _REDACTED),
]

# ── JSON API response rules ─────────────────────────────────────────────────
_JSON_RULES: list[tuple[re.Pattern[str], str]] = [
    # Catches "password": "value", "secret": "value", "community": "value",
    # "presharedKey": "value", "sharedSecret": "value" etc.
    (
        re.compile(
            r'("(?:[Pp]ass[Ww]ord|[Ss]ecret|[Cc]ommunity|[Pp]re[Ss]hared[Kk]ey'
            r"|[Ss]hared[Ss]ecret|[Pp]sk|[Aa]uth[Kk]ey|[Pp]rivacy[Pp]assword"
            r"|[Kk]ey[Cc]hain|[Ee]nable[Ss]ecret|[Ee]nable[Pp]assword"
            r"|snmpAuthPassword|snmpPrivPassword"
            r')"\s*:\s*)"[^"]*"'
        ),
        r'\1"' + _REDACTED + '"',
    ),
]


def _looks_like_json(text: str) -> bool:
    """Return True if *text* appears to be a JSON response."""
    stripped = text.lstrip()
    return stripped[:1] in ("{", "[")


def sanitize_output(text: str) -> str:
    """Apply redaction rules to *text* and return the sanitized copy.

    Selects CLI or JSON rules based on a content heuristic: output starting
    with ``{`` or ``[`` (after whitespace) is treated as JSON, everything
    else as CLI text.

    The rule list is short and the 50 KB input cap in
    :meth:`~collector.TestResultCollector.add_command_api_execution` keeps
    runtime negligible.
    """
    rules = _JSON_RULES if _looks_like_json(text) else _CLI_RULES
    for pattern, replacement in rules:
        text = pattern.sub(replacement, text)
    return text
