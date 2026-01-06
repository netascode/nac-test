# PRD: PyATS Common Consolidation Architecture

## Executive Summary

This PRD addresses the architectural challenge of duplicated `pyats_common/` directories across NAC architecture repositories (ACI, SD-WAN, Catalyst Center). The goal is to consolidate shared PyATS testing infrastructure—including auth classes, test base classes, and device resolvers—into a centralized, maintainable package.

**Status**: DRAFT v5.3 - Simplified migration for net new codebase

---

## Problem Statement

### Current State

Each NAC architecture repository contains a duplicated `pyats_common/` directory:

| Repository | Location | Files |
|------------|----------|-------|
| nac-catalystcenter-terraform | `tests/templates/catc/test/pyats_common/` | `catc_auth.py`, `catc_base_test.py` |
| nac-sdwan-terraform | `tests/templates/cedge/test/pyats_common/` | `vmanage_auth.py`, `vmanage_base_test.py`, `sdwan_base_test.py`, `sdwan_device_resolver.py` |
| ACI-as-Code-Demo | `aac/tests/templates/apic/test/pyats_common/` | `apic_auth.py`, `apic_base_test.py` |

### Pain Points

1. **Code Duplication**: ~90% of base test class code is identical across architectures
2. **Implementation Drift**: Bug fixes or improvements must be manually propagated to all repos
3. **Maintenance Burden**: Each architecture team maintains essentially the same code
4. **Testing Complexity**: Changes require testing across multiple repositories
5. **Fragile Imports**: Current import pattern (`from templates.catc.test.pyats_common...`) is non-standard and breaks easily
6. **Scalability Issues**: Adding new architectures (ISE, Meraki, IOS-XE, etc.) compounds the problem

---

## Codebase Analysis: What Goes Where

### Analysis of Current nac-test Components

| Component | Location | Architecture-Specific? | Decision |
|-----------|----------|------------------------|----------|
| `TestbedGenerator` | nac-test/execution/device/ | **NO** - 100% generic | **STAYS in nac-test** |
| `DeviceInventoryDiscovery` | nac-test/discovery/ | **NO** - contract-based | **STAYS in nac-test** |
| `ConnectionBroker` | nac-test/broker/ | **NO** - uses generic testbed | **STAYS in nac-test** |
| `NACTestBase` | nac-test/common/ | **NO** - generic base | **STAYS in nac-test** |
| `SSHTestBase` | nac-test/common/ | **NO** - generic SSH base | **STAYS in nac-test** |
| `AuthCache` | nac-test/common/ | **NO** - generic caching | **STAYS in nac-test** |
| Orchestrator | nac-test/orchestrator/ | **NO** - generic runner | **STAYS in nac-test** |
| HTML Report Generator | nac-test/reporting/ | **NO** - generic reporting | **STAYS in nac-test** |

### Analysis of pyats_common Components (Currently Duplicated)

| Component | Architecture-Specific? | Decision |
|-----------|------------------------|----------|
| Auth classes (APICAuth, VManageAuth, CatalystCenterAuth) | **YES** - different endpoints, tokens, headers | **MOVE to nac-test-pyats-common** |
| Test base classes (APICTestBase, VManageTestBase, etc.) | **YES** - architecture-specific setup, client creation | **MOVE to nac-test-pyats-common** |
| Device resolvers (SDWANDeviceResolver) | **YES** - parse NAC schemas | **MOVE to nac-test-pyats-common** |

### Key Design Principle: Separation of Concerns

**nac-test's responsibilities** (should NOT change):
- Test orchestration (discovering tests, running them)
- Testbed generation (generic device dict → PyATS YAML)
- Connection brokering (SSH connection pooling)
- HTML report generation
- Progress tracking and output processing
- Generic base classes (NACTestBase, SSHTestBase)

**nac-test-pyats-common's responsibilities** (NEW):
- Architecture-specific authentication (APICAuth, VManageAuth, CatalystCenterAuth)
- Architecture-specific test base classes (APICTestBase, VManageTestBase, etc.)
- Architecture-specific client configuration (headers, SSL settings)
- Architecture-specific device resolvers (SDWANDeviceResolver, etc.)

**Architecture repo responsibilities** (simplified):
- Test files (verify_*.py)
- NAC schema definitions

---

## Final Architecture Decision

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│               Layer 3: Architecture Repositories                     │
│     (nac-aci-terraform, nac-sdwan-terraform, nac-catc-terraform)    │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐                          │
│  │ Test Files      │  │ NAC Schema      │                          │
│  │ (verify_*.py)   │  │ Definitions     │                          │
│  └────────┬────────┘  └─────────────────┘                          │
│           │                                                          │
│           │ imports                                                  │
│           ▼                                                          │
└───────────┼──────────────────────────────────────────────────────────┘
            │
┌───────────▼──────────────────────────────────────────────────────────┐
│       Layer 2: nac-test-pyats-common (Architecture Adapters)        │
│                    DEPENDS ON nac-test                               │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  nac_test_pyats_common/                                      │   │
│  │  ├── __init__.py          # Version + public exports         │   │
│  │  ├── py.typed             # PEP 561 marker                   │   │
│  │  ├── base.py              # AuthBaseProtocol (abstract)      │   │
│  │  │                                                           │   │
│  │  ├── aci/                 # ACI/APIC adapter                 │   │
│  │  │   ├── __init__.py      # Exports APICAuth, APICTestBase   │   │
│  │  │   ├── auth.py          # APICAuth implementation          │   │
│  │  │   └── test_base.py     # APICTestBase (extends NACTestBase)│   │
│  │  │                                                           │   │
│  │  ├── sdwan/               # SD-WAN adapter                   │   │
│  │  │   ├── __init__.py      # Exports VManageAuth, etc.        │   │
│  │  │   ├── auth.py          # VManageAuth implementation       │   │
│  │  │   ├── api_test_base.py # VManageTestBase                  │   │
│  │  │   ├── ssh_test_base.py # SDWANSSHTestBase                 │   │
│  │  │   └── device_resolver.py # SDWANDeviceResolver            │   │
│  │  │                                                           │   │
│  │  └── catc/                # Catalyst Center adapter          │   │
│  │      ├── __init__.py      # Exports CatalystCenterAuth, etc. │   │
│  │      ├── auth.py          # CatalystCenterAuth impl          │   │
│  │      └── test_base.py     # CatalystCenterTestBase           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                       │                                              │
│                       │ imports NACTestBase, SSHTestBase, AuthCache │
│                       ▼                                              │
└───────────────────────┼──────────────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────────────┐
│                Layer 1: nac-test (Core Framework)                    │
│                    Orchestration + Generic Infrastructure            │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  nac_test/pyats_core/                                        │   │
│  │  │                                                           │   │
│  │  ├── common/                 # Generic base infrastructure   │   │
│  │  │   ├── base_test.py        # NACTestBase                   │   │
│  │  │   ├── ssh_base_test.py    # SSHTestBase                   │   │
│  │  │   ├── auth_cache.py       # AuthCache (generic caching)   │   │
│  │  │   └── connection_pool.py  # Connection pooling            │   │
│  │  │                                                           │   │
│  │  ├── orchestrator/           # Test orchestration            │   │
│  │  │   ├── protocols.py        # DeviceResolverProtocol        │   │
│  │  │   └── orchestrator.py     # Main orchestration            │   │
│  │  │                                                           │   │
│  │  ├── execution/device/       # Test execution                │   │
│  │  │   └── testbed_generator.py # Generic testbed generation   │   │
│  │  │                                                           │   │
│  │  ├── broker/                 # Connection management         │   │
│  │  │   └── connection_broker.py # SSH connection pooling       │   │
│  │  │                                                           │   │
│  │  ├── reporting/              # HTML report generation        │   │
│  │  │   ├── generator.py                                        │   │
│  │  │   └── multi_archive_generator.py                          │   │
│  │  │                                                           │   │
│  │  └── discovery/              # Test & device discovery       │   │
│  │      └── device_inventory.py # Contract-based discovery      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Dependencies: pyats, httpx, pyyaml, jinja2, rich, etc.             │
└─────────────────────────────────────────────────────────────────────┘
```

### Why Auth + Test Bases Live Together in nac-test-pyats-common

**The Skeptic's Argument (Accepted)**:
1. Auth classes and test base classes form a **cohesive adapter layer** for each architecture
2. Test bases USE auth classes directly - they're tightly coupled
3. Separating them creates artificial boundaries
4. Architecture repos should import **one unified adapter** per architecture

**nac-test's Job is to RUN Tests, Not Define Them**:
- nac-test is the orchestrator/runner/reporter
- Adding architecture-specific test bases to nac-test bloats its responsibility
- nac-test should remain architecture-agnostic

**Dependency Direction**:
- `nac-test-pyats-common` depends on `nac-test` (for NACTestBase, AuthCache)
- This is correct: adapters (higher-level) depend on generic infrastructure (lower-level)
- No circular dependencies

### Why Device Resolvers Also Move to nac-test-pyats-common

**Device resolvers are tightly coupled with test base classes** - they parse NAC schemas to provide device inventory for tests. Consolidating them in nac-test-pyats-common:

1. **Complete Adapter Layer**: Auth + test bases + device resolvers form a complete architecture adapter
2. **Single Package Import**: Architecture repos import everything from one package
3. **Consistent Maintenance**: All architecture-specific code in one place
4. **Protocol Compliance**: Device resolvers implement `DeviceResolverProtocol` from nac-test

**Import Pattern**:
```python
# In architecture repo test files
from nac_test_pyats_common.sdwan import VManageTestBase, SDWANDeviceResolver
```

---

## Package Name

### Decision: `nac-test-pyats-common`

| Aspect | Value |
|--------|-------|
| **PyPI Package Name** | `nac-test-pyats-common` |
| **Python Import Name** | `nac_test_pyats_common` |
| **Repository Name** | `netascode/nac-test-pyats-common` |

### Rationale

1. **nac-test-**: Clearly shows this is part of the nac-test ecosystem
2. **pyats-**: Clarifies this is PyATS infrastructure (not Robot, not generic)
3. **common**: Indicates shared code across architectures

---

## Import Patterns

### Test Files in Architecture Repos

```python
# In nac-catalystcenter-terraform/tests/templates/catc/test/api/verify_*.py

# BEFORE (fragile)
from templates.catc.test.pyats_common.catc_base_test import CatalystCenterTestBase

# AFTER (clean)
from nac_test_pyats_common.catc import CatalystCenterTestBase
from nac_test.pyats_core.reporting.types import ResultStatus
```

### Test Base Classes in nac-test-pyats-common

```python
# In nac_test_pyats_common/catc/test_base.py

import os
from typing import Any
from pyats import aetest

from nac_test.pyats_core.common.base_test import NACTestBase
from nac_test.pyats_core.common.auth_cache import AuthCache

from .auth import CatalystCenterAuth


class CatalystCenterTestBase(NACTestBase):
    """Catalyst Center API test base class.

    Extends NACTestBase with Catalyst Center-specific:
    - Token-based authentication (X-Auth-Token header)
    - Controller URL and SSL configuration from environment
    - API client creation with tracking
    """

    @aetest.setup
    def setup(self) -> None:
        """Setup method that obtains auth and creates client."""
        super().setup()

        # Get auth data (uses AuthCache internally)
        self.auth_data = CatalystCenterAuth.get_auth()

        # Environment config
        self.controller_url = os.environ.get("CC_URL", "").rstrip("/")
        insecure = os.environ.get("CC_INSECURE", "True").lower() in ("true", "1", "yes")
        self.verify_ssl = not insecure

        # Client creation (uses NACTestBase.pool)
        self.client = self._create_client()

    def _create_client(self) -> Any:
        """Create httpx client with Catalyst Center auth headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Auth-Token": self.auth_data["token"],
        }
        base_client = self.pool.get_client(
            base_url=self.controller_url,
            headers=headers,
            verify=self.verify_ssl,
        )
        return self.wrap_client_for_tracking(base_client, device_name="CatalystCenter")

    # run_async_verification_test() inherited from NACTestBase - no reimplementation needed!
```

### Auth Classes in nac-test-pyats-common

```python
# In nac_test_pyats_common/catc/auth.py

import os
from typing import Any
import httpx

from nac_test.pyats_core.common.auth_cache import AuthCache


class CatalystCenterAuth:
    """Catalyst Center authentication adapter.

    Handles token-based authentication using Basic Auth POST.
    Supports both modern and legacy auth endpoints for version compatibility.
    Uses AuthCache for process-safe token management.
    """

    AUTH_ENDPOINTS = [
        "/api/system/v1/auth/token",      # Modern (Catalyst Center 2.x)
        "/dna/system/api/v1/auth/token",  # Legacy (DNA Center 1.x/2.x)
    ]

    DEFAULT_TTL_SECONDS = 3600  # 1 hour

    @classmethod
    def _authenticate(
        cls, url: str, username: str, password: str, verify_ssl: bool
    ) -> tuple[dict[str, Any], int]:
        """Perform authentication and return auth data with TTL."""
        with httpx.Client(verify=verify_ssl, timeout=30.0) as client:
            for endpoint in cls.AUTH_ENDPOINTS:
                try:
                    response = client.post(
                        f"{url}{endpoint}",
                        auth=(username, password),
                        headers={"Content-Type": "application/json"},
                    )
                    response.raise_for_status()
                    token = response.json().get("Token")
                    if token:
                        return {"token": str(token)}, cls.DEFAULT_TTL_SECONDS
                except httpx.HTTPError:
                    continue
        raise RuntimeError("Authentication failed on all endpoints")

    @classmethod
    def get_auth(cls) -> dict[str, Any]:
        """Get auth data with caching.

        Uses AuthCache for process-safe token management with automatic
        TTL-based refresh.

        Returns:
            Dict containing token

        Raises:
            ValueError: If required environment variables not set
        """
        url = os.environ.get("CC_URL", "").rstrip("/")
        username = os.environ.get("CC_USERNAME", "")
        password = os.environ.get("CC_PASSWORD", "")
        insecure = os.environ.get("CC_INSECURE", "True").lower() in ("true", "1", "yes")

        if not all([url, username, password]):
            raise ValueError("Missing CC_URL, CC_USERNAME, or CC_PASSWORD")

        return AuthCache.get_or_create(
            controller_type="CC",
            url=url,
            auth_func=lambda: cls._authenticate(url, username, password, not insecure),
        )
```

---

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEPENDENCY FLOW                               │
│                                                                  │
│   Architecture Repos                                            │
│   ├── nac-aci-terraform                                         │
│   ├── nac-sdwan-terraform                                       │
│   └── nac-catc-terraform                                        │
│           │                                                      │
│           │ pip install nac-test-pyats-common                   │
│           ▼                                                      │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │            nac-test-pyats-common                           │ │
│   │   • Auth classes (APICAuth, VManageAuth, etc.)            │ │
│   │   • Test base classes (APICTestBase, VManageTestBase)     │ │
│   │   • Architecture-specific client configuration            │ │
│   └───────────────────────────────────────────────────────────┘ │
│           │                                                      │
│           │ pip install nac-test (dependency)                   │
│           ▼                                                      │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │                      nac-test                              │ │
│   │   • Test orchestration                                     │ │
│   │   • Generic base classes (NACTestBase, SSHTestBase)       │ │
│   │   • AuthCache, connection pooling                         │ │
│   │   • Testbed generation                                     │ │
│   │   • Connection broker                                      │ │
│   │   • HTML report generation                                 │ │
│   │   • DeviceResolverProtocol                                │ │
│   └───────────────────────────────────────────────────────────┘ │
│           │                                                      │
│           │ pip install pyats, httpx, etc.                      │
│           ▼                                                      │
│       [pyats, httpx, pyyaml, jinja2, rich, etc.]               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Points**:
1. **Architecture repos only need `pip install nac-test-pyats-common`** - it brings nac-test as transitive dependency
2. **No circular dependencies** - clean unidirectional flow
3. **nac-test stays focused** - orchestration, reporting, generic infrastructure only

---

## Versioning Strategy

### Semantic Versioning (SemVer)

Both packages follow [Semantic Versioning 2.0.0](https://semver.org/):

```
MAJOR.MINOR.PATCH

MAJOR: Breaking API changes
MINOR: New features, backward compatible
PATCH: Bug fixes, backward compatible
```

### Dependency Declaration: Compatible Release Pinning

```toml
# In nac-test-pyats-common/pyproject.toml
[project]
dependencies = [
    "nac-test~=1.1.0",  # >=1.1.0, <2.0.0
]
```

### Release Coordination Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    Release Flow                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. PATCH RELEASE (Bug Fix)                                     │
│     ┌──────────────────────────┐                                │
│     │ nac-test-pyats-common    │ v1.0.0 → v1.0.1               │
│     │ (bug fix in auth class)  │                                │
│     └──────────────────────────┘                                │
│            │                                                     │
│            ▼                                                     │
│     Architecture repos automatically get fix (no action needed) │
│                                                                  │
│  2. MINOR RELEASE (New Feature)                                 │
│     ┌──────────────────────────┐                                │
│     │ nac-test-pyats-common    │ v1.0.x → v1.1.0               │
│     │ (new auth type: ISE)     │                                │
│     └──────────────────────────┘                                │
│            │                                                     │
│            ▼                                                     │
│     ┌──────────────────────────┐                                │
│     │ Architecture repos       │ Optional: update to use new   │
│     │                          │ ISE auth if needed             │
│     └──────────────────────────┘                                │
│                                                                  │
│  3. MAJOR RELEASE (Breaking Change)                             │
│     ┌──────────────────────────┐                                │
│     │ nac-test-pyats-common    │ v1.x.x → v2.0.0               │
│     │ (API signature change)   │                                │
│     └──────────────────────────┘                                │
│            │                                                     │
│            ▼                                                     │
│     ┌──────────────────────────┐                                │
│     │ Architecture repos       │ MUST update imports/usage     │
│     │                          │ to match new API              │
│     └──────────────────────────┘                                │
│                                                                  │
│  4. nac-test RELEASE (Framework Change)                         │
│     ┌──────────────────────────┐                                │
│     │ nac-test                 │ v1.1.x → v1.2.0               │
│     │ (new NACTestBase method) │                                │
│     └──────────────────────────┘                                │
│            │                                                     │
│            ▼                                                     │
│     ┌──────────────────────────┐                                │
│     │ nac-test-pyats-common    │ Optional: release to use new  │
│     │                          │ feature if beneficial         │
│     └──────────────────────────┘                                │
│            │                                                     │
│            ▼                                                     │
│     Architecture repos get new nac-test via transitive dep      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Version Compatibility Matrix

| nac-test-pyats-common | nac-test Required | Notes |
|-----------------------|-------------------|-------|
| 1.0.x | ~=1.1.0 | Initial release |
| 1.1.x | ~=1.1.0 | New architecture added |
| 2.0.x | ~=2.0.0 | Breaking changes require nac-test 2.0 |

### Breaking Change Policy

| Change Type | Version Bump | Examples |
|-------------|--------------|----------|
| Bug fix (no API change) | PATCH (1.0.x) | Fix auth token parsing, fix SSL handling |
| New architecture added | MINOR (1.x.0) | Add ISEAuth, MerakiTestBase |
| New optional parameter | MINOR (1.x.0) | Add `timeout` param with default |
| **Method signature change** | **MAJOR (x.0.0)** | Change `get_auth()` return type |
| **Remove public API** | **MAJOR (x.0.0)** | Remove deprecated auth class |
| **Rename public class** | **MAJOR (x.0.0)** | APICAuth → ACIAuth |

### Version Compatibility Check (Required)

```python
# In nac_test_pyats_common/__init__.py
from importlib.metadata import version
from packaging.version import Version
import sys

__version__ = "1.0.0"

# Critical method signatures that MUST exist in nac-test
_REQUIRED_NAC_TEST_METHODS = [
    ("nac_test.pyats_core.common.base_test", "NACTestBase", "setup"),
    ("nac_test.pyats_core.common.base_test", "NACTestBase", "cleanup"),
    ("nac_test.pyats_core.common.auth_cache", "AuthCache", "get_or_create"),
]

def _check_nac_test_compatibility():
    """Runtime check for compatible nac-test version and method signatures."""
    import importlib

    # Version check
    try:
        nac_test_version = Version(version("nac-test"))
        if nac_test_version.major != 1 or nac_test_version.minor < 1:
            raise ImportError(
                f"nac-test {nac_test_version} is incompatible. "
                f"nac-test-pyats-common {__version__} requires nac-test>=1.1.0,<2.0.0"
            )
    except Exception as e:
        if "nac-test" in str(e).lower():
            raise  # Re-raise version mismatch errors
        # Package not installed - will fail on actual import anyway

    # Method signature check (critical APIs)
    for module_path, class_name, method_name in _REQUIRED_NAC_TEST_METHODS:
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            if not hasattr(cls, method_name):
                raise ImportError(
                    f"nac-test is missing required method: {class_name}.{method_name}. "
                    f"Please upgrade nac-test to a compatible version."
                )
        except ModuleNotFoundError:
            raise ImportError(
                f"nac-test module not found: {module_path}. "
                f"Please install nac-test>=1.1.0"
            )

_check_nac_test_compatibility()
```

### Integration Test for Cross-Package Compatibility

```python
# In nac-test-pyats-common/tests/integration/test_nac_test_compatibility.py

import pytest
from importlib.metadata import version

def test_nac_test_version_compatible():
    """Verify nac-test version is within compatible range."""
    from packaging.version import Version
    nac_test_ver = Version(version("nac-test"))
    assert nac_test_ver >= Version("1.1.0")
    assert nac_test_ver < Version("2.0.0")

def test_required_base_classes_importable():
    """Verify critical nac-test classes can be imported."""
    from nac_test.pyats_core.common.base_test import NACTestBase
    from nac_test.pyats_core.common.ssh_base_test import SSHTestBase
    from nac_test.pyats_core.common.auth_cache import AuthCache

    assert hasattr(NACTestBase, "setup")
    assert hasattr(NACTestBase, "cleanup")
    assert hasattr(AuthCache, "get_or_create")

def test_auth_cache_signature_compatible():
    """Verify AuthCache.get_or_create has expected signature."""
    from nac_test.pyats_core.common.auth_cache import AuthCache
    import inspect

    sig = inspect.signature(AuthCache.get_or_create)
    params = list(sig.parameters.keys())

    # Required parameters
    assert "controller_type" in params
    assert "url" in params
    assert "auth_func" in params
```

---

## Device Resolver Contract

### Protocol Definition (in nac-test)

```python
# In nac_test/pyats_core/orchestrator/protocols.py

from typing import Protocol, Dict, List, Any

class DeviceResolverProtocol(Protocol):
    """Contract for architecture-specific device inventory resolution.

    Architecture repos implement this to parse their NAC schemas
    (sites.nac.yaml, test_inventory.yaml, etc.) and return device
    dictionaries compatible with nac-test's TestbedGenerator.
    """

    @classmethod
    def get_ssh_device_inventory(cls, data_model: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse data model and return device inventory.

        Args:
            data_model: Merged NAC data model (YAML parsed to dict)

        Returns:
            List of device dictionaries, each containing:
            - hostname: str (required)
            - host: str - IP address (required)
            - os: str - operating system type (required)
            - username: str (required)
            - password: str (required)
            - port: int (optional, default 22)
            - connection_options: dict (optional)
        """
        ...
```

### Implementation (in nac-test-pyats-common)

```python
# In nac_test_pyats_common/sdwan/device_resolver.py

import os
from typing import Dict, List, Any
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nac_test.pyats_core.orchestrator.protocols import DeviceResolverProtocol

class SDWANDeviceResolver:  # Implements DeviceResolverProtocol
    """SD-WAN specific device resolver - parses sites.nac.yaml schema."""

    @classmethod
    def get_ssh_device_inventory(cls, data_model: Dict[str, Any]) -> List[Dict[str, Any]]:
        devices = []
        for site in data_model.get("sdwan", {}).get("sites", []):
            for router in site.get("routers", []):
                devices.append({
                    "hostname": router["device_variables"]["system_hostname"],
                    "host": router["device_variables"]["mgmt_ip"],
                    "os": "iosxe",
                    "username": os.environ.get("SDWAN_USERNAME"),
                    "password": os.environ.get("SDWAN_PASSWORD"),
                })
        return devices
```

---

## Testbed Generator Extensibility

### Current State

`TestbedGenerator` in nac-test is 100% generic. It converts device dictionaries to PyATS testbed YAML.

### Future Extensibility (If Needed)

If architecture-specific testbed logic is ever needed:

```python
# In nac_test/pyats_core/execution/device/testbed_generator.py

from typing import Protocol

class TestbedGeneratorProtocol(Protocol):
    """Protocol for testbed generation - allows future extension."""

    def generate_testbed_yaml(self, device: dict) -> str: ...
    def generate_consolidated_testbed_yaml(self, devices: list[dict]) -> str: ...

class TestbedGenerator:
    """Default generic implementation."""
    # Current implementation...

# FUTURE: If needed, architecture-specific generators can implement the protocol
# and be registered with the orchestrator
```

**Current Decision**: No architecture-specific testbed generation needed. Keep `TestbedGenerator` generic. Add extensibility only if future requirements demand it.

---

## Critical Prerequisites (Phase 0)

> **CRITICAL**: The following must be completed BEFORE any migration work begins.

### 1. Create DeviceResolverProtocol in nac-test

**Current State**: `DeviceResolverProtocol` is referenced throughout this PRD but **DOES NOT EXIST** in the nac-test codebase. The current `DeviceInventoryDiscovery` class dynamically imports test modules to find resolvers - there is no formal protocol contract.

**Required Action**: Create the protocol file in nac-test FIRST:

```python
# NEW FILE: nac_test/pyats_core/orchestrator/protocols.py

from typing import Protocol, Dict, List, Any, runtime_checkable

@runtime_checkable
class DeviceResolverProtocol(Protocol):
    """Contract for architecture-specific device inventory resolution.

    Architecture repos implement this to parse their NAC schemas
    (sites.nac.yaml, test_inventory.yaml, etc.) and return device
    dictionaries compatible with nac-test's TestbedGenerator.

    This is a structural subtyping protocol - implementations do NOT
    need to explicitly inherit from this class. They just need to
    provide the required method signature.
    """

    @classmethod
    def get_ssh_device_inventory(cls, data_model: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse data model and return device inventory.

        Args:
            data_model: Merged NAC data model (YAML parsed to dict)

        Returns:
            List of device dictionaries, each containing:
            - hostname: str (required)
            - host: str - IP address (required)
            - os: str - operating system type (required)
            - username: str (required)
            - password: str (required)
            - port: int (optional, default 22)
            - connection_options: dict (optional)
        """
        ...
```

**Verification**: Run `grep -r "DeviceResolverProtocol" nac_test/` should return results after this step.

### 2. Verify Type Checking Across Package Boundaries

**Risk**: Circular imports can occur through type hints even when runtime imports are safe.

**Required Action**: Before publishing nac-test-pyats-common v1.0.0, run:

```bash
# In nac-test-pyats-common repo
mypy --strict src/nac_test_pyats_common/

# Verify no circular import errors
python -c "from nac_test_pyats_common.aci import APICTestBase; print('OK')"
python -c "from nac_test_pyats_common.sdwan import VManageTestBase; print('OK')"
python -c "from nac_test_pyats_common.catc import CatalystCenterTestBase; print('OK')"
```

**Import Safety Pattern**: Use `TYPE_CHECKING` guard for type-only imports:

```python
# In nac_test_pyats_common/aci/test_base.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # These imports are only for type hints, not runtime
    from nac_test.pyats_core.common.base_test import NACTestBase

# Runtime import (always safe)
from nac_test.pyats_core.common.base_test import NACTestBase  # OK - no circular dep
```

### 3. Constants Coupling Resolution

**Issue**: `AuthCache` imports `AUTH_CACHE_DIR` from `nac_test.pyats_core.constants`. When nac-test-pyats-common imports `AuthCache`, it inherits this coupling.

**Resolution**: This is **acceptable and intentional**. The cache directory MUST be shared across packages to prevent:
- Cache misses (auth performed multiple times)
- Stale tokens (different cache locations)
- File lock conflicts

**Documented Contract**:
- `AUTH_CACHE_DIR` is defined in `nac_test.pyats_core.constants`
- All packages using `AuthCache` share this directory
- nac-test owns this constant; nac-test-pyats-common does NOT redefine it

---

## Migration Plan

### Phase 1: Create nac-test-pyats-common Package

1. **Create repository**: `netascode/nac-test-pyats-common`
2. **Package structure**:
   ```
   nac-test-pyats-common/
   ├── pyproject.toml
   ├── README.md
   ├── src/nac_test_pyats_common/
   │   ├── __init__.py         # Version + compatibility check
   │   ├── py.typed
   │   ├── base.py             # AuthBaseProtocol
   │   ├── aci/
   │   │   ├── __init__.py     # __all__ = ['APICAuth', 'APICTestBase', 'ACIDeviceResolver']
   │   │   ├── auth.py         # APICAuth
   │   │   ├── test_base.py    # APICTestBase
   │   │   └── device_resolver.py # ACIDeviceResolver (if applicable)
   │   ├── sdwan/
   │   │   ├── __init__.py     # __all__ = ['VManageAuth', 'VManageTestBase', 'SDWANSSHTestBase', 'SDWANDeviceResolver']
   │   │   ├── auth.py         # VManageAuth
   │   │   ├── api_test_base.py # VManageTestBase
   │   │   ├── ssh_test_base.py # SDWANSSHTestBase
   │   │   └── device_resolver.py # SDWANDeviceResolver
   │   └── catc/
   │       ├── __init__.py     # __all__ = ['CatalystCenterAuth', 'CatalystCenterTestBase', 'CatalystCenterDeviceResolver']
   │       ├── auth.py         # CatalystCenterAuth
   │       ├── test_base.py    # CatalystCenterTestBase
   │       └── device_resolver.py # CatalystCenterDeviceResolver (if applicable)
   └── tests/
       ├── conftest.py
       ├── test_aci_auth.py
       ├── test_sdwan_auth.py
       └── test_catc_auth.py
   ```
3. **Copy auth + test base classes + device resolvers** from architecture repos
4. **Update imports** to use nac-test for base classes
5. **Add unit tests** with mocked HTTP responses
6. **Publish to PyPI**: v1.0.0

### Phase 2: Update Architecture Repositories

For each architecture repo:

1. **Add dependency**: Add `nac-test-pyats-common` to requirements
2. **Update all test file imports** to use new package:
   ```python
   # Old (remove)
   from templates.xxx.test.pyats_common.xxx_base_test import XXXTestBase
   # New (add)
   from nac_test_pyats_common.xxx import XXXTestBase
   ```
3. **Delete `pyats_common/` directory** entirely (all code now in nac-test-pyats-common)
4. **Run full test suite** to verify functionality
5. **Commit changes**

### Phase 3: Update nac-test

> **NOTE**: DeviceResolverProtocol creation is now in **Phase 0 (Prerequisites)** and MUST be completed before Phase 1.

1. **Verify DeviceResolverProtocol** exists in `orchestrator/protocols.py` (from Phase 0)
2. **Export protocol** in package `__init__.py` for architecture repo type hints
3. **No other changes needed** - nac-test stays focused on orchestration

---

## Error Handling Strategy

### Cross-Package Error Propagation

When errors occur in nac-test-pyats-common (e.g., auth failures), they must surface clearly to users.

#### Error Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                    ERROR FLOW                                    │
│                                                                  │
│  User sees:                                                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ nac_test_pyats_common.catc.auth.CatalystCenterAuth:         ││
│  │ Authentication failed - Invalid credentials for CC_URL      ││
│  │                                                              ││
│  │ Caused by: httpx.HTTPStatusError: 401 Unauthorized          ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  NOT this (bad):                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ RuntimeError: Authentication failed on all endpoints        ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

#### Custom Exception Classes

```python
# In nac_test_pyats_common/exceptions.py

class NACPyATSCommonError(Exception):
    """Base exception for nac-test-pyats-common package."""
    pass

class AuthenticationError(NACPyATSCommonError):
    """Raised when controller authentication fails.

    Attributes:
        controller_type: Type of controller (ACI, CC, VMANAGE)
        url: Controller URL (sanitized - no credentials)
        cause: Original exception that caused the failure
    """
    def __init__(self, controller_type: str, url: str, cause: Exception | None = None):
        self.controller_type = controller_type
        self.url = url
        self.cause = cause
        message = f"{controller_type} authentication failed for {url}"
        if cause:
            message += f": {cause}"
        super().__init__(message)

class EnvironmentConfigError(NACPyATSCommonError):
    """Raised when required environment variables are missing."""
    def __init__(self, missing_vars: list[str], controller_type: str):
        self.missing_vars = missing_vars
        self.controller_type = controller_type
        message = f"Missing required environment variables for {controller_type}: {', '.join(missing_vars)}"
        super().__init__(message)
```

#### Auth Class Error Handling Pattern

```python
# In nac_test_pyats_common/catc/auth.py

from nac_test_pyats_common.exceptions import AuthenticationError, EnvironmentConfigError

class CatalystCenterAuth:
    @classmethod
    def get_auth(cls) -> dict[str, Any]:
        url = os.environ.get("CC_URL", "").rstrip("/")
        username = os.environ.get("CC_USERNAME", "")
        password = os.environ.get("CC_PASSWORD", "")

        # Clear error for missing env vars
        missing = []
        if not url: missing.append("CC_URL")
        if not username: missing.append("CC_USERNAME")
        if not password: missing.append("CC_PASSWORD")
        if missing:
            raise EnvironmentConfigError(missing, "CatalystCenter")

        try:
            return AuthCache.get_or_create(
                controller_type="CC",
                url=url,
                auth_func=lambda: cls._authenticate(url, username, password, ...),
            )
        except httpx.HTTPStatusError as e:
            raise AuthenticationError("CatalystCenter", url, cause=e) from e
        except httpx.ConnectError as e:
            raise AuthenticationError("CatalystCenter", url, cause=e) from e
```

#### Logging Strategy

| Package | Log Level | What to Log |
|---------|-----------|-------------|
| nac-test-pyats-common | DEBUG | Auth attempts, token refresh, cache hits/misses |
| nac-test-pyats-common | INFO | Auth success, controller type detected |
| nac-test-pyats-common | WARNING | Deprecated endpoints used, SSL verification disabled |
| nac-test-pyats-common | ERROR | Auth failures (with sanitized details) |
| nac-test | INFO | Test execution progress |
| nac-test | ERROR | Test failures, orchestration errors |

**NEVER LOG**: Passwords, tokens, API keys, or full credentials.

---

## Success Criteria (Quantitative)

| Criterion | Metric | Target | Measurement Method |
|-----------|--------|--------|-------------------|
| **Code Duplication** | Lines of duplicated code | 0 | `jscpd` duplicate detector across repos |
| **Import Time** | Package import duration | < 500ms | `python -X importtime -c "from nac_test_pyats_common import ..."` |
| **Test Coverage** | Line + branch coverage | ≥ 95% | `pytest --cov --cov-branch` |
| **Type Safety** | mypy errors | 0 | `mypy --strict src/` |
| **Regression Tests** | Existing tests passing | 100% | CI/CD pipeline in all architecture repos |
| **Performance** | Test execution time delta | ≤ 5% increase | Benchmark before/after migration |
| **Package Size** | Installed size | < 1 MB | `pip show nac-test-pyats-common` |
| **Documentation** | Public API coverage | 100% | All public classes/functions have docstrings |

### Qualitative Success Criteria

1. **Zero code duplication**: No `pyats_common/` directories in architecture repos
2. **Single source of truth**: Auth classes + test bases + device resolvers in nac-test-pyats-common
3. **Clean imports**: `from nac_test_pyats_common.xxx import XXXTestBase`
4. **Correct dependency direction**: nac-test-pyats-common → nac-test
5. **nac-test unchanged**: Orchestration, reporting, generic infrastructure only
6. **No circular dependencies**: Clean unidirectional dependency flow verified by import tests

---

## Scalability Considerations

### Adding New Architectures (ISE, Meraki, IOS-XE)

**For Controller-Based Architectures** (ISE, Meraki):
1. Add to nac-test-pyats-common:
   - `ise/auth.py` → ISEAuth
   - `ise/test_base.py` → ISETestBase
   - `ise/device_resolver.py` → ISEDeviceResolver (if D2D tests needed)
2. Architecture repo uses: `from nac_test_pyats_common.ise import ISETestBase, ISEDeviceResolver`

**For Device-Only Architectures** (IOS-XE direct SSH):
1. May not need auth class (uses SSH credentials)
2. Add to nac-test-pyats-common:
   - `iosxe/ssh_test_base.py` → IOSXESSHTestBase (extends SSHTestBase)
   - `iosxe/device_resolver.py` → IOSXEDeviceResolver

**For Cloud-Based Architectures** (Meraki):
1. Add to nac-test-pyats-common:
   - `meraki/auth.py` → MerakiAuth (API key based)
   - `meraki/test_base.py` → MerakiTestBase
2. No device resolver needed (no SSH to devices)

---

## Contributor Guide

### Post-Migration: Where to Make Changes

After migration, contributors need to understand which repository to modify:

| Change Type | Repository | Example |
|-------------|------------|---------|
| **Auth endpoint change** | nac-test-pyats-common | Catalyst Center adds new auth API |
| **Auth header format** | nac-test-pyats-common | APIC changes cookie format |
| **Test base setup logic** | nac-test-pyats-common | Add new setup step for all CC tests |
| **Generic orchestration** | nac-test | Change how tests are discovered/run |
| **HTML report format** | nac-test | Modify report template |
| **AuthCache behavior** | nac-test | Change TTL logic, cache directory |
| **Device resolver logic** | nac-test-pyats-common | Parse new schema field |
| **Test file (verify_*.py)** | Architecture repo | Add new verification test |
| **NAC schema changes** | Architecture repo | Add new data model field |

### Local Development Setup

For contributors working across packages:

```bash
# Clone all three repos
git clone https://github.com/netascode/nac-test.git
git clone https://github.com/netascode/nac-test-pyats-common.git
git clone https://github.com/netascode/nac-catalystcenter-terraform.git  # or other arch repo

# Install nac-test in editable mode
cd nac-test
uv pip install -e ".[dev]"

# Install nac-test-pyats-common in editable mode (uses local nac-test)
cd ../nac-test-pyats-common
uv pip install -e ".[dev]"

# Now architecture repo uses local versions
cd ../nac-catalystcenter-terraform
uv pip install -e ".[dev]"  # Will use local nac-test-pyats-common
```

### Testing Changes Across Packages

When modifying nac-test-pyats-common:

```bash
# 1. Run unit tests in nac-test-pyats-common
cd nac-test-pyats-common
uv run pytest tests/unit/ -v

# 2. Run integration tests (requires nac-test)
uv run pytest tests/integration/ -v

# 3. Run architecture repo tests to verify no regressions
cd ../nac-catalystcenter-terraform
uv run pytest tests/ -v --tb=short
```

---

## Known Limitations & TODOs

### TODO: File-Based Locking Portability

**Current State**: `AuthCache` in nac-test uses `fcntl.flock()` for process-safe token caching:

```python
# nac_test/pyats_core/common/auth_cache.py line 49
with open(lock_file, "w") as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
```

**Limitation**: `fcntl` is Unix-only and may behave unexpectedly on:
- Windows (not supported)
- NFS/network filesystems (locking semantics vary)
- Some containerized CI/CD environments with shared `/tmp`

**Impact**: This is an **existing limitation** in nac-test, not introduced by this migration. The forklift migration preserves current behavior.

**Future Work** (out of scope for this PRD):
- [ ] Evaluate cross-platform locking alternatives (`filelock` library)
- [ ] Consider Redis/memcached for distributed environments
- [ ] Add CI environment detection to warn about potential issues

**Current Mitigation**: Document that nac-test requires Unix-like environment (Linux, macOS).

---

## Appendix A: pyproject.toml Templates

### nac-test-pyats-common

```toml
[project]
name = "nac-test-pyats-common"
version = "1.0.0"
description = "Architecture adapters for NAC PyATS testing (auth + test base classes)"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "nac-test~=1.1.0",  # Core framework dependency (brings pyats as transitive dep)
    "httpx>=0.28",       # HTTP client for auth
]
# NOTE: Do NOT pin pyats here. nac-test already pins pyats~=25.5.
# This package inherits pyats version from nac-test to avoid conflicts.
# This follows Django ecosystem pattern: django-rest-framework doesn't pin Django.

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
    "pytest-asyncio>=0.23",
    "respx>=0.21",  # For mocking httpx
    "ruff>=0.4",
    "mypy>=1.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/nac_test_pyats_common"]
```

---

## Appendix B: Full Package Structure

```
nac-test-pyats-common/
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── src/
│   └── nac_test_pyats_common/
│       ├── __init__.py              # Version, exports, compatibility check
│       ├── py.typed                 # PEP 561 marker
│       ├── base.py                  # AuthBaseProtocol
│       │
│       ├── aci/
│       │   ├── __init__.py          # __all__ = ['APICAuth', 'APICTestBase', 'ACIDeviceResolver']
│       │   ├── auth.py              # APICAuth
│       │   ├── test_base.py         # APICTestBase
│       │   └── device_resolver.py   # ACIDeviceResolver (if applicable)
│       │
│       ├── sdwan/
│       │   ├── __init__.py          # __all__ = ['VManageAuth', 'VManageTestBase', 'SDWANSSHTestBase', 'SDWANDeviceResolver']
│       │   ├── auth.py              # VManageAuth
│       │   ├── api_test_base.py     # VManageTestBase (API tests)
│       │   ├── ssh_test_base.py     # SDWANSSHTestBase (D2D/SSH tests)
│       │   └── device_resolver.py   # SDWANDeviceResolver
│       │
│       └── catc/
│           ├── __init__.py          # __all__ = ['CatalystCenterAuth', 'CatalystCenterTestBase', 'CatalystCenterDeviceResolver']
│           ├── auth.py              # CatalystCenterAuth
│           ├── test_base.py         # CatalystCenterTestBase
│           └── device_resolver.py   # CatalystCenterDeviceResolver (if applicable)
│
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_aci_auth.py
    │   ├── test_sdwan_auth.py
    │   └── test_catc_auth.py
    └── integration/
        └── test_full_flow.py        # Optional: integration with nac-test
```

---

*Document Version: 5.3*
*Author: Claude (AI Assistant)*
*Date: December 2025*
*Status: DRAFT - Ready for implementation planning*
*Revision History:*
- *v1.0: Initial proposal (rejected - incorrect dependency direction)*
- *v2.0: Revised per architectural reviewer (partial)*
- *v3.0: Auth only in adapter package, test bases in nac-test*
- *v4.0: Auth + test bases consolidated in nac-test-pyats-common per skeptic/user feedback*
- *v5.0: Addresses skeptic review findings:*
  - *Added Phase 0 prerequisites (DeviceResolverProtocol creation)*
  - *Added circular import risk mitigation (TYPE_CHECKING pattern)*
  - *Expanded version compatibility (method signature checks, breaking change policy)*
  - *Resolved AUTH_CACHE_DIR coupling (documented as intentional)*
  - *Added error propagation strategy (custom exceptions, logging policy)*
  - *Added quantitative success criteria (measurable targets)*
- *v5.1: Refinements after source code review:*
  - *Added PyATS version inheritance strategy (nac-test pins, others inherit)*
  - *Added Contributor Guide (where to make changes post-migration)*
  - *Added Known Limitations & TODOs (fcntl.flock portability)*
- *v5.2: Device resolver decision change:*
  - *Device resolvers now MOVE to nac-test-pyats-common (not stay in architecture repos)*
  - *Updated architecture diagram, package structure, contributor guide*
  - *Complete adapter layer: Auth + Test Bases + Device Resolvers all consolidated*
- *v5.3: Simplified migration (net new codebase):*
  - *Removed phased rollback strategy - not needed for MVP*
  - *Removed deprecation timeline - no existing users to migrate*
  - *Simplified Phase 2 to direct migration*
