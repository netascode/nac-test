# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Backward-compatible re-export — AuthCache moved to nac_test.core.auth_cache.

This shim exists for nac-test-pyats-common's main branch which still
imports from this path. Remove once all consumers use the new path.
"""

from nac_test.core.auth_cache import AuthCache

__all__ = ["AuthCache"]
