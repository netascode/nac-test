# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Bridge-release compatibility shim.

Re-exports only the controller symbols actually used by ``nac-test-pyats-common``:
- detect_controller_type (iosxe/test_base.py)
- get_matched_credential_set (sdwan/auth.py)

This shim exists so that ``nac-test-pyats-common`` continues to work during the
transition window. It will be removed after all consumers have migrated to
``nac_test.core.controller`` (Phase 3 of the controller-resolution refactor).
"""

from nac_test.core.controller import (  # noqa: F401
    detect_controller_type,
    get_matched_credential_set,
)
