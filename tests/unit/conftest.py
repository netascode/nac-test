# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared fixtures for unit tests."""

import os

import pytest
from _pytest.monkeypatch import MonkeyPatch

CONTROLLER_ENV_PREFIXES = ("ACI_", "SDWAN_", "CC_", "MERAKI_", "FMC_", "ISE_")


@pytest.fixture()
def clean_controller_env(monkeypatch: MonkeyPatch) -> None:
    """Clear all controller-related environment variables.

    Ensures tests run in isolation regardless of the caller's shell environment.
    """
    for key in list(os.environ.keys()):
        if any(prefix in key for prefix in CONTROLLER_ENV_PREFIXES):
            monkeypatch.delenv(key, raising=False)
