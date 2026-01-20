# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

"""PyATS discovery components."""

from .device_inventory import DeviceInventoryDiscovery
from .test_discovery import TestDiscovery

__all__ = [
    "TestDiscovery",
    "DeviceInventoryDiscovery",
]
