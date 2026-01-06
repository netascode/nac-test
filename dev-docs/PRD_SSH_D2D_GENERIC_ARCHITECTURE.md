# PRD: Generic SSH/Direct-to-Device Architecture

## Executive Summary

This PRD addresses the architectural need to decouple SSH/Direct-to-Device (D2D) testing infrastructure from SD-WAN-specific implementation. The goal is to create a scalable, reusable foundation that supports 15+ network architectures (SD-WAN, ACI, Catalyst Center, NDFC, IOS-XR, Meraki, FMC, traditional IOS-XE, NX-OS, etc.) without code duplication.

**Status**: DRAFT v1.0

---

## Problem Statement

### Current State

The SSH/D2D testing infrastructure is tightly coupled to SD-WAN:

| Component | Location | Problem |
|-----------|----------|---------|
| `SDWANTestBase` | nac-test-pyats-common/sdwan/ | Hardcoded SD-WAN paths, env vars, schema navigation |
| `SDWANDeviceResolver` | nac-test-pyats-common/sdwan/ | Tightly coupled to SD-WAN data model (sites, routers, chassis_id) |
| Credential handling | SDWANTestBase | Uses `SDWAN_USERNAME`/`SDWAN_PASSWORD` (wrong - should be `IOSXE_USERNAME`/`IOSXE_PASSWORD` for D2D) |

### Pain Points

1. **Tight Coupling**: D2D infrastructure assumes SD-WAN schema structure
2. **Wrong Credentials**: SD-WAN D2D uses controller env vars instead of device-specific env vars
3. **No Reusability**: Adding ACI D2D or Catalyst Center D2D would require copy-pasting and adapting
4. **Schema Lock-in**: Device resolution logic hardcoded to SD-WAN's `sites[].routers[].device_variables` structure
5. **Scalability Nightmare**: 15 architectures = 15 copies of similar code with subtle differences

### Future Scale

- **Current**: 1 D2D implementation (SD-WAN)
- **Near-term**: ACI (NX-OS switches), Catalyst Center (IOS-XE devices)
- **Future**: NDFC, IOS-XR, Meraki, FMC, traditional IOS-XE, NX-OS direct, and more

---

## Design Principle: Build for Scale

> "Make it nice or make it twice."

Rather than waiting to see patterns emerge across 2-3 implementations, we're building the architecture now with full knowledge that 15+ architectures are coming. This avoids costly refactoring later.

---

## Solution Architecture

### Three-Layer Design

```
Layer 1: nac-test (Core Framework)
├── pyats_core/common/
│   └── ssh_base_test.py           # SSHTestBase (existing, enhanced with validation)
├── utils/
│   ├── file_discovery.py          # Generic directory traversal (NEW)
│   └── device_validation.py       # Device dict validation (NEW)

Layer 2: nac-test-pyats-common (Architecture Adapters)
├── src/nac_test_pyats_common/
│   ├── common/
│   │   └── base_device_resolver.py    # BaseDeviceResolver with abstract methods (NEW)
│   ├── sdwan/
│   │   ├── device_resolver.py         # SDWANDeviceResolver (refactored to extend base)
│   │   └── ssh_test_base.py           # SDWANTestBase (refactored to use correct creds)
│   ├── aci/
│   │   ├── device_resolver.py         # ACIDeviceResolver (future)
│   │   └── ssh_test_base.py           # ACISSHTestBase (future)
│   ├── catc/
│   │   ├── device_resolver.py         # CatalystCenterDeviceResolver (future)
│   │   └── ssh_test_base.py           # CatalystCenterSSHTestBase (future)
│   └── iosxe/
│       └── ... (future architectures follow same pattern)

Layer 3: Architecture Repos
└── tests/d2d/*.py                 # Import from Layer 2
```

---

## Component Specifications

### 1. Device Validation Utility (nac-test)

**Location**: `nac_test/utils/device_validation.py`

```python
"""Device inventory validation utilities.

Validates device dictionaries before SSH connection attempts,
catching configuration errors early rather than failing mid-test.
"""

from typing import Any


REQUIRED_DEVICE_FIELDS: frozenset[str] = frozenset({
    "hostname",
    "host",
    "os",
    "username",
    "password",
})


class DeviceValidationError(ValueError):
    """Raised when device dictionary validation fails.

    Attributes:
        device_index: Index of the invalid device in the list.
        device_hostname: Hostname of the device (if available).
        missing_fields: Set of missing required fields.
        invalid_fields: Dict of field name to validation error message.
    """

    def __init__(
        self,
        device_index: int,
        device_hostname: str | None,
        missing_fields: set[str] | None = None,
        invalid_fields: dict[str, str] | None = None,
    ) -> None:
        self.device_index = device_index
        self.device_hostname = device_hostname
        self.missing_fields = missing_fields or set()
        self.invalid_fields = invalid_fields or {}

        parts = [f"Device {device_index}"]
        if device_hostname:
            parts[0] = f"Device {device_index} ({device_hostname})"

        if self.missing_fields:
            parts.append(f"missing required fields: {self.missing_fields}")
        if self.invalid_fields:
            for field, error in self.invalid_fields.items():
                parts.append(f"{field}: {error}")

        super().__init__(" - ".join(parts))


def validate_device_inventory(
    devices: list[dict[str, Any]],
    *,
    raise_on_first_error: bool = True,
) -> list[DeviceValidationError]:
    """Validate device dictionaries have required fields before connection.

    This function should be called by SSHTestBase before attempting SSH
    connections to catch configuration errors early.

    Args:
        devices: List of device dictionaries to validate.
        raise_on_first_error: If True, raise on first validation error.
            If False, collect all errors and return them.

    Returns:
        List of validation errors (empty if all devices valid).
        Only populated if raise_on_first_error is False.

    Raises:
        DeviceValidationError: If validation fails and raise_on_first_error is True.

    Example:
        >>> devices = [{"hostname": "router1", "host": "10.1.1.1", "os": "iosxe"}]
        >>> validate_device_inventory(devices)  # Raises - missing username/password
        DeviceValidationError: Device 0 (router1) - missing required fields: {'username', 'password'}
    """
    errors: list[DeviceValidationError] = []

    for i, device in enumerate(devices):
        hostname = device.get("hostname")
        missing = REQUIRED_DEVICE_FIELDS - set(device.keys())

        if missing:
            error = DeviceValidationError(
                device_index=i,
                device_hostname=hostname,
                missing_fields=missing,
            )
            if raise_on_first_error:
                raise error
            errors.append(error)
            continue

        # Validate field values (not just presence)
        invalid: dict[str, str] = {}

        if not isinstance(device["hostname"], str) or not device["hostname"]:
            invalid["hostname"] = "must be a non-empty string"
        if not isinstance(device["host"], str) or not device["host"]:
            invalid["host"] = "must be a non-empty string (IP address)"
        if not isinstance(device["os"], str) or not device["os"]:
            invalid["os"] = "must be a non-empty string (e.g., 'iosxe', 'nxos')"
        if device["username"] is None:
            invalid["username"] = "must not be None (check environment variables)"
        if device["password"] is None:
            invalid["password"] = "must not be None (check environment variables)"

        if invalid:
            error = DeviceValidationError(
                device_index=i,
                device_hostname=hostname,
                invalid_fields=invalid,
            )
            if raise_on_first_error:
                raise error
            errors.append(error)

    return errors
```

### 2. File Discovery Utility (nac-test)

**Location**: `nac_test/utils/file_discovery.py`

```python
"""Generic file discovery utilities.

Provides directory traversal logic for finding configuration files
(test_inventory.yaml, etc.) without architecture-specific knowledge.
"""

import logging
from pathlib import Path


logger = logging.getLogger(__name__)


def find_data_file(
    filename: str,
    start_path: Path | None = None,
    search_dirs: list[str] | None = None,
) -> Path | None:
    """Find a data file by traversing up the directory tree.

    Searches for a file by traversing up from the start path, looking
    in common data directories at each level.

    Args:
        filename: Name of the file to find (e.g., "test_inventory.yaml").
        start_path: Starting path for the search. Defaults to current working directory.
        search_dirs: List of directory names to search within at each level.
            Defaults to ["data", "config", "inventory"].

    Returns:
        Path to the file if found, None otherwise.

    Example:
        >>> # Find test_inventory.yaml starting from a test file's location
        >>> inventory_path = find_data_file(
        ...     "test_inventory.yaml",
        ...     start_path=Path(__file__).parent
        ... )
    """
    if search_dirs is None:
        search_dirs = ["data", "config", "inventory"]

    current_path = start_path or Path.cwd()
    current_path = current_path.resolve()

    # Traverse up the directory tree
    while current_path.parent != current_path:  # Not at filesystem root
        for search_dir in search_dirs:
            data_dir = current_path / search_dir
            if data_dir.exists() and data_dir.is_dir():
                candidate = data_dir / filename
                if candidate.exists():
                    logger.debug(f"Found {filename} at {candidate}")
                    return candidate

        # Also check current directory directly
        direct_candidate = current_path / filename
        if direct_candidate.exists():
            logger.debug(f"Found {filename} at {direct_candidate}")
            return direct_candidate

        current_path = current_path.parent

    logger.warning(f"Could not find {filename} starting from {start_path}")
    return None
```

### 3. BaseDeviceResolver (nac-test-pyats-common)

**Location**: `src/nac_test_pyats_common/common/base_device_resolver.py`

This is the core abstraction - a base class with the Template Method pattern that handles common logic while delegating schema-specific work to abstract methods.

```python
"""Base device resolver for SSH/D2D testing.

Provides the Template Method pattern for device inventory resolution.
Architecture-specific resolvers extend this class and implement the
abstract methods for schema navigation and credential retrieval.
"""

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml

from nac_test.utils.file_discovery import find_data_file


logger = logging.getLogger(__name__)


class BaseDeviceResolver(ABC):
    """Abstract base class for architecture-specific device resolvers.

    This class implements the Template Method pattern for device inventory
    resolution. It handles common logic (inventory loading, credential
    injection, device dict construction) while delegating schema-specific
    work to abstract methods.

    Subclasses MUST implement:
        - get_architecture_name(): Return architecture identifier (e.g., "sdwan")
        - get_schema_root_key(): Return the root key in data model (e.g., "sdwan")
        - navigate_to_devices(): Navigate schema to get iterable of device data
        - extract_device_id(): Extract unique device identifier from device data
        - extract_hostname(): Extract hostname from device data
        - extract_host_ip(): Extract management IP from device data
        - extract_os_type(): Extract OS type from device data
        - get_credential_env_vars(): Return (username_env_var, password_env_var)

    Subclasses MAY override:
        - get_inventory_filename(): Return inventory filename (default: "test_inventory.yaml")
        - build_device_dict(): Customize device dict construction
        - _load_inventory(): Customize inventory loading

    Attributes:
        data_model: The merged NAC data model dictionary.
        test_inventory: The test inventory dictionary (devices to test).

    Example:
        >>> class SDWANDeviceResolver(BaseDeviceResolver):
        ...     def get_architecture_name(self) -> str:
        ...         return "sdwan"
        ...
        ...     def get_schema_root_key(self) -> str:
        ...         return "sdwan"
        ...
        ...     # ... implement other abstract methods ...
        >>>
        >>> resolver = SDWANDeviceResolver(data_model)
        >>> devices = resolver.get_resolved_inventory()
    """

    def __init__(
        self,
        data_model: dict[str, Any],
        test_inventory: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the device resolver.

        Args:
            data_model: The merged NAC data model containing all architecture
                data with resolved variables.
            test_inventory: Optional test inventory specifying which devices
                to test. If not provided, will attempt to load from file.
        """
        self.data_model = data_model
        self.test_inventory = test_inventory or self._load_inventory()

    def _load_inventory(self) -> dict[str, Any]:
        """Load test inventory from file.

        Searches for the inventory file using the generic file discovery
        utility. Subclasses can override this to customize loading behavior.

        Returns:
            Test inventory dictionary, or empty dict if not found.
        """
        filename = self.get_inventory_filename()
        inventory_path = find_data_file(filename)

        if inventory_path is None:
            logger.warning(
                f"Test inventory file '{filename}' not found for "
                f"{self.get_architecture_name()}. Using empty inventory."
            )
            return {}

        logger.info(f"Loading test inventory from {inventory_path}")
        try:
            with open(inventory_path) as f:
                raw_data = yaml.safe_load(f) or {}

            # Support both nested and flat formats:
            # Nested: {arch: {test_inventory: {...}}}
            # Flat: {test_inventory: {...}}
            arch_key = self.get_schema_root_key()
            if arch_key in raw_data and "test_inventory" in raw_data[arch_key]:
                return raw_data[arch_key]["test_inventory"]
            elif "test_inventory" in raw_data:
                return raw_data["test_inventory"]
            else:
                return raw_data

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse test inventory YAML: {e}")
            return {}
        except OSError as e:
            logger.error(f"Failed to read test inventory file: {e}")
            return {}

    def get_resolved_inventory(self) -> list[dict[str, Any]]:
        """Get resolved device inventory ready for SSH connection.

        This is the main entry point. It:
        1. Navigates the data model to find device data
        2. Matches devices against test inventory (if provided)
        3. Extracts hostname, IP, OS from each device
        4. Injects SSH credentials from environment variables
        5. Returns list of device dicts ready for nac-test

        Returns:
            List of device dictionaries with all required fields:
            - hostname (str)
            - host (str)
            - os (str)
            - username (str)
            - password (str)
            - Plus any architecture-specific fields
        """
        logger.info(f"Resolving device inventory for {self.get_architecture_name()}")

        resolved_devices: list[dict[str, Any]] = []
        devices_to_test = self._get_devices_to_test()

        for device_data in devices_to_test:
            try:
                device_dict = self.build_device_dict(device_data)
                resolved_devices.append(device_dict)
            except (KeyError, ValueError) as e:
                device_id = self._safe_extract_device_id(device_data)
                logger.warning(
                    f"Skipping device {device_id}: {e}"
                )
                continue

        # Inject credentials
        self._inject_credentials(resolved_devices)

        logger.info(
            f"Resolved {len(resolved_devices)} devices for "
            f"{self.get_architecture_name()} D2D testing"
        )
        return resolved_devices

    def _get_devices_to_test(self) -> list[dict[str, Any]]:
        """Get the list of device data dicts to process.

        If test_inventory specifies devices, filter to only those.
        Otherwise, return all devices from the data model.

        Returns:
            List of device data dictionaries from the data model.
        """
        all_devices = list(self.navigate_to_devices())

        # If no test inventory, test all devices
        inventory_devices = self.test_inventory.get("devices", [])
        if not inventory_devices:
            return all_devices

        # Build index for efficient lookup
        device_index: dict[str, dict[str, Any]] = {}
        for device_data in all_devices:
            device_id = self._safe_extract_device_id(device_data)
            if device_id:
                device_index[device_id] = device_data

        # Filter to devices in test inventory
        devices_to_test: list[dict[str, Any]] = []
        for inventory_entry in inventory_devices:
            device_id = self._get_device_id_from_inventory(inventory_entry)
            if device_id in device_index:
                # Merge inventory entry data with device data
                merged = {**device_index[device_id], **inventory_entry}
                devices_to_test.append(merged)
            else:
                logger.warning(
                    f"Device '{device_id}' from test_inventory not found in "
                    f"{self.get_architecture_name()} data model"
                )

        return devices_to_test

    def _get_device_id_from_inventory(self, inventory_entry: dict[str, Any]) -> str:
        """Extract device ID from a test inventory entry.

        Override this if your inventory uses a different field name.

        Args:
            inventory_entry: Entry from test_inventory.devices[]

        Returns:
            Device identifier string.
        """
        # Common patterns across architectures
        for key in ["chassis_id", "device_id", "node_id", "hostname", "name"]:
            if key in inventory_entry:
                return str(inventory_entry[key])
        return ""

    def _safe_extract_device_id(self, device_data: dict[str, Any]) -> str:
        """Safely extract device ID, returning empty string on failure."""
        try:
            return self.extract_device_id(device_data)
        except (KeyError, ValueError):
            return "<unknown>"

    def build_device_dict(self, device_data: dict[str, Any]) -> dict[str, Any]:
        """Build a device dictionary from raw device data.

        Override this method to customize device dict construction
        for your architecture.

        Args:
            device_data: Raw device data from the data model.

        Returns:
            Device dictionary with hostname, host, os fields.
            Credentials are injected separately.
        """
        return {
            "hostname": self.extract_hostname(device_data),
            "host": self.extract_host_ip(device_data),
            "os": self.extract_os_type(device_data),
            "device_id": self.extract_device_id(device_data),
        }

    def _inject_credentials(self, devices: list[dict[str, Any]]) -> None:
        """Inject SSH credentials from environment variables.

        Args:
            devices: List of device dicts to update in place.
        """
        username_var, password_var = self.get_credential_env_vars()
        username = os.environ.get(username_var)
        password = os.environ.get(password_var)

        if not username:
            logger.warning(f"Environment variable {username_var} not set")
        if not password:
            logger.warning(f"Environment variable {password_var} not set")

        for device in devices:
            device["username"] = username
            device["password"] = password

    # -------------------------------------------------------------------------
    # Abstract methods - MUST be implemented by subclasses
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_architecture_name(self) -> str:
        """Return the architecture identifier.

        Used for logging and error messages.

        Returns:
            Architecture name (e.g., "sdwan", "aci", "catc").
        """
        ...

    @abstractmethod
    def get_schema_root_key(self) -> str:
        """Return the root key in the data model for this architecture.

        Used when loading test inventory and navigating the schema.

        Returns:
            Root key (e.g., "sdwan", "apic", "cc").
        """
        ...

    @abstractmethod
    def navigate_to_devices(self) -> list[dict[str, Any]]:
        """Navigate the data model to find all devices.

        This is where architecture-specific schema navigation happens.
        Implement this to traverse your NAC schema structure.

        Returns:
            Iterable of device data dictionaries from the data model.

        Example (SD-WAN):
            >>> def navigate_to_devices(self):
            ...     devices = []
            ...     for site in self.data_model.get("sdwan", {}).get("sites", []):
            ...         devices.extend(site.get("routers", []))
            ...     return devices
        """
        ...

    @abstractmethod
    def extract_device_id(self, device_data: dict[str, Any]) -> str:
        """Extract unique device identifier from device data.

        This ID is used to match test_inventory entries with data model devices.

        Args:
            device_data: Device data dict from navigate_to_devices().

        Returns:
            Unique device identifier string.

        Example (SD-WAN):
            >>> def extract_device_id(self, device_data):
            ...     return device_data["chassis_id"]
        """
        ...

    @abstractmethod
    def extract_hostname(self, device_data: dict[str, Any]) -> str:
        """Extract device hostname from device data.

        Args:
            device_data: Device data dict from navigate_to_devices().

        Returns:
            Device hostname string.

        Example (SD-WAN):
            >>> def extract_hostname(self, device_data):
            ...     return device_data["device_variables"]["system_hostname"]
        """
        ...

    @abstractmethod
    def extract_host_ip(self, device_data: dict[str, Any]) -> str:
        """Extract management IP address from device data.

        Should handle any IP formatting (e.g., strip CIDR notation).

        Args:
            device_data: Device data dict from navigate_to_devices().

        Returns:
            IP address string (e.g., "10.1.1.100").

        Example (SD-WAN):
            >>> def extract_host_ip(self, device_data):
            ...     ip_var = device_data.get("management_ip_variable", "mgmt_ip")
            ...     ip = device_data["device_variables"].get(ip_var, "")
            ...     return ip.split("/")[0] if "/" in ip else ip
        """
        ...

    @abstractmethod
    def extract_os_type(self, device_data: dict[str, Any]) -> str:
        """Extract operating system type from device data.

        Args:
            device_data: Device data dict from navigate_to_devices().

        Returns:
            OS type string (e.g., "iosxe", "nxos", "iosxr").

        Example (SD-WAN):
            >>> def extract_os_type(self, device_data):
            ...     return device_data.get("os", "iosxe")
        """
        ...

    @abstractmethod
    def get_credential_env_vars(self) -> tuple[str, str]:
        """Return environment variable names for SSH credentials.

        Each architecture uses different env vars for device credentials.
        These are separate from controller credentials.

        Returns:
            Tuple of (username_env_var, password_env_var).

        Example (SD-WAN D2D uses IOS-XE devices):
            >>> def get_credential_env_vars(self):
            ...     return ("IOSXE_USERNAME", "IOSXE_PASSWORD")

        Example (ACI D2D uses NX-OS switches):
            >>> def get_credential_env_vars(self):
            ...     return ("NXOS_SSH_USERNAME", "NXOS_SSH_PASSWORD")
        """
        ...

    # -------------------------------------------------------------------------
    # Optional overrides
    # -------------------------------------------------------------------------

    def get_inventory_filename(self) -> str:
        """Return the test inventory filename.

        Override to use a different filename.

        Returns:
            Filename (default: "test_inventory.yaml").
        """
        return "test_inventory.yaml"
```

### 4. Refactored SDWANDeviceResolver

**Location**: `src/nac_test_pyats_common/sdwan/device_resolver.py`

```python
"""SD-WAN-specific device resolver for parsing the NAC data model.

This module provides the SDWANDeviceResolver class, which extends
BaseDeviceResolver to implement SD-WAN schema navigation.
"""

import logging
from typing import Any

from nac_test_pyats_common.common.base_device_resolver import BaseDeviceResolver


logger = logging.getLogger(__name__)


class SDWANDeviceResolver(BaseDeviceResolver):
    """SD-WAN device resolver for D2D testing.

    Navigates the SD-WAN NAC schema (sites[].routers[]) to extract
    device information for SSH testing.

    Schema structure:
        sdwan:
          sites:
            - name: "site1"
              routers:
                - chassis_id: "abc123"
                  device_variables:
                    system_hostname: "router1"
                    vpn10_mgmt_ip: "10.1.1.100/32"

    Credentials:
        Uses IOSXE_USERNAME and IOSXE_PASSWORD environment variables
        because SD-WAN edge devices are IOS-XE based.
    """

    def get_architecture_name(self) -> str:
        """Return 'sdwan' as the architecture identifier."""
        return "sdwan"

    def get_schema_root_key(self) -> str:
        """Return 'sdwan' as the root key in the data model."""
        return "sdwan"

    def navigate_to_devices(self) -> list[dict[str, Any]]:
        """Navigate SD-WAN schema: sdwan.sites[].routers[].

        Returns:
            List of router dictionaries from all sites.
        """
        devices: list[dict[str, Any]] = []
        sdwan_data = self.data_model.get("sdwan", {})

        for site in sdwan_data.get("sites", []):
            routers = site.get("routers", [])
            devices.extend(routers)

        return devices

    def extract_device_id(self, device_data: dict[str, Any]) -> str:
        """Extract chassis_id as the device identifier."""
        chassis_id = device_data.get("chassis_id")
        if not chassis_id:
            raise ValueError("Router missing 'chassis_id' field")
        return str(chassis_id)

    def extract_hostname(self, device_data: dict[str, Any]) -> str:
        """Extract hostname from device_variables.system_hostname."""
        device_vars = device_data.get("device_variables", {})

        if "system_hostname" in device_vars:
            return str(device_vars["system_hostname"])

        # Fallback to chassis_id
        chassis_id = device_data.get("chassis_id", "unknown")
        logger.warning(
            f"No system_hostname found for {chassis_id}, using chassis_id as hostname"
        )
        return str(chassis_id)

    def extract_host_ip(self, device_data: dict[str, Any]) -> str:
        """Extract management IP from device_variables.

        Handles CIDR notation (e.g., "10.1.1.100/32" -> "10.1.1.100").
        Uses management_ip_variable field to determine which variable
        contains the management IP.
        """
        device_vars = device_data.get("device_variables", {})

        # Get the variable name that contains the management IP
        ip_var = device_data.get("management_ip_variable")

        if ip_var and ip_var in device_vars:
            ip_value = str(device_vars[ip_var])
        else:
            # Fallback: try common variable names
            for fallback_var in ["mgmt_ip", "management_ip", "vpn0_ip"]:
                if fallback_var in device_vars:
                    ip_value = str(device_vars[fallback_var])
                    break
            else:
                raise ValueError(
                    f"Could not find management IP for device. "
                    f"Set 'management_ip_variable' in test_inventory or use "
                    f"standard variable names (mgmt_ip, management_ip, vpn0_ip)."
                )

        # Strip CIDR notation if present
        if "/" in ip_value:
            ip_value = ip_value.split("/")[0]

        return ip_value

    def extract_os_type(self, device_data: dict[str, Any]) -> str:
        """Extract OS type, defaulting to 'iosxe' for SD-WAN edges."""
        return device_data.get("os", "iosxe")

    def get_credential_env_vars(self) -> tuple[str, str]:
        """Return IOS-XE credential env vars for SD-WAN edge devices.

        SD-WAN D2D tests connect to IOS-XE based edge devices,
        NOT the vManage/SDWAN Manager controller.
        """
        return ("IOSXE_USERNAME", "IOSXE_PASSWORD")
```

### 5. Refactored SDWANTestBase

**Location**: `src/nac_test_pyats_common/sdwan/ssh_test_base.py`

The SSH test base becomes simpler - it just implements the `get_ssh_device_inventory` contract using the resolver.

```python
"""SD-WAN specific base test class for SSH/Direct-to-Device testing.

This module provides the SDWANTestBase class, which extends the generic SSHTestBase
to add SD-WAN-specific functionality for device-to-device (D2D) testing.
"""

import logging
from typing import Any

from nac_test.pyats_core.common.ssh_base_test import SSHTestBase  # type: ignore[import-untyped]

from .device_resolver import SDWANDeviceResolver


logger = logging.getLogger(__name__)


class SDWANTestBase(SSHTestBase):  # type: ignore[misc]
    """SD-WAN-specific base test class for SSH/D2D testing.

    This class extends the generic SSHTestBase to provide SD-WAN-specific
    device inventory resolution for D2D testing via SSH.

    The class implements the DeviceInventoryProvider contract required by
    nac-test's orchestrator for device discovery.

    Credentials:
        Uses IOSXE_USERNAME and IOSXE_PASSWORD environment variables
        because SD-WAN edge devices are IOS-XE based. This is different
        from SDWAN_USERNAME/SDWAN_PASSWORD which are for the controller.

    Example:
        class VerifyBGPPeers(SDWANTestBase):
            async def get_items_to_verify(self):
                # Return items to verify
                return self.data_model.get("bgp_peers", [])

            async def verify_item(self, item):
                # SSH verification logic
                output = await self.execute_command("show ip bgp summary")
                return item["neighbor"] in output
    """

    @classmethod
    def get_ssh_device_inventory(
        cls, data_model: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Parse the SD-WAN data model to retrieve the device inventory.

        This method is the entry point called by nac-test's orchestrator.
        It delegates to SDWANDeviceResolver for schema navigation and
        credential injection.

        Args:
            data_model: The merged data model from nac-test containing all
                SD-WAN sites.nac.yaml data with resolved variables.

        Returns:
            List of device dictionaries ready for SSH connection, each containing:
            - hostname (str): Device hostname
            - host (str): Management IP address
            - os (str): Operating system (typically "iosxe")
            - username (str): SSH username from IOSXE_USERNAME env var
            - password (str): SSH password from IOSXE_PASSWORD env var
            - device_id (str): chassis_id for data model navigation
        """
        logger.info(
            "SDWANTestBase: Delegating device inventory retrieval to SDWANDeviceResolver."
        )

        resolver = SDWANDeviceResolver(data_model)
        return resolver.get_resolved_inventory()
```

---

## Integration with Existing Code

### SSHTestBase Enhancement

Add validation call in `SSHTestBase.setup()`:

```python
# In nac_test/pyats_core/common/ssh_base_test.py

from nac_test.utils.device_validation import validate_device_inventory, DeviceValidationError

class SSHTestBase(NACTestBase):
    @aetest.setup
    def setup(self) -> None:
        super().setup()

        device_info_json = os.environ.get("DEVICE_INFO")
        # ... existing code ...

        try:
            self.device_info = json.loads(device_info_json)
        except json.JSONDecodeError as e:
            self.failed(f"Could not parse device info: {e}")
            return

        # NEW: Validate device info before connection attempt
        try:
            validate_device_inventory([self.device_info])
        except DeviceValidationError as e:
            self.failed(
                f"Device validation failed: {e}\n"
                "Check that the device resolver is returning all required fields "
                "and that credential environment variables are set."
            )
            return

        # ... rest of setup ...
```

---

## Migration Plan

### Phase 1: Add Core Infrastructure (nac-test)

1. Create `nac_test/utils/device_validation.py` with validation utility
2. Create `nac_test/utils/file_discovery.py` with generic file discovery
3. Update `SSHTestBase.setup()` to call validation
4. Run tests, ensure no regressions

### Phase 2: Add Base Resolver (nac-test-pyats-common)

1. Create `src/nac_test_pyats_common/common/` directory
2. Create `src/nac_test_pyats_common/common/__init__.py` with exports
3. Create `src/nac_test_pyats_common/common/base_device_resolver.py` with `BaseDeviceResolver`
4. Run tests

### Phase 3: Refactor SD-WAN (nac-test-pyats-common)

1. Refactor `SDWANDeviceResolver` to extend `BaseDeviceResolver`
2. Update `SDWANTestBase` to use refactored resolver
3. **Fix credential env vars**: Change from `SDWAN_USERNAME`/`SDWAN_PASSWORD` to `IOSXE_USERNAME`/`IOSXE_PASSWORD`
4. Run tests, ensure no regressions

### Phase 4: Documentation

1. Update existing PRD_AND_ARCHITECTURE.md with new patterns
2. Add architecture implementation guide for future architectures
3. Document credential naming conventions per architecture

---

## Future Architecture Template

When adding a new architecture (e.g., ACI D2D), developers create:

```python
# src/nac_test_pyats_common/aci/device_resolver.py

class ACIDeviceResolver(BaseDeviceResolver):
    def get_architecture_name(self) -> str:
        return "aci"

    def get_schema_root_key(self) -> str:
        return "apic"

    def navigate_to_devices(self) -> list[dict[str, Any]]:
        # ACI-specific: navigate to leaf/spine nodes
        nodes = []
        for node in self.data_model.get("apic", {}).get("nodes", []):
            if node.get("role") in ["leaf", "spine"]:
                nodes.append(node)
        return nodes

    def extract_device_id(self, device_data: dict[str, Any]) -> str:
        return device_data["node_id"]

    def extract_hostname(self, device_data: dict[str, Any]) -> str:
        return device_data["name"]

    def extract_host_ip(self, device_data: dict[str, Any]) -> str:
        return device_data["oob_mgmt_ip"]

    def extract_os_type(self, device_data: dict[str, Any]) -> str:
        return "nxos"

    def get_credential_env_vars(self) -> tuple[str, str]:
        return ("NXOS_SSH_USERNAME", "NXOS_SSH_PASSWORD")
```

---

## Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Code duplication | 0 lines of duplicated resolver logic | Diff analysis |
| New architecture effort | < 100 lines of code | Line count for new resolver |
| Test coverage | >= 90% on base_device_resolver.py | pytest --cov |
| SD-WAN D2D tests pass | 100% | CI pipeline |
| Validation catches errors | Before SSH connection | Unit tests |

---

## Appendix: Credential Environment Variables

| Architecture | D2D Device Type | Username Env Var | Password Env Var |
|--------------|-----------------|------------------|------------------|
| SD-WAN | IOS-XE edges | `IOSXE_USERNAME` | `IOSXE_PASSWORD` |
| ACI | NX-OS switches | `NXOS_SSH_USERNAME` | `NXOS_SSH_PASSWORD` |
| Catalyst Center | IOS-XE devices | `IOSXE_USERNAME` | `IOSXE_PASSWORD` |
| NDFC | NX-OS switches | `NXOS_SSH_USERNAME` | `NXOS_SSH_PASSWORD` |
| IOS-XE Direct | IOS-XE devices | `IOSXE_USERNAME` | `IOSXE_PASSWORD` |
| IOS-XR | IOS-XR devices | `IOSXR_USERNAME` | `IOSXR_PASSWORD` |

**Note**: These are device-specific credentials, separate from controller API credentials (e.g., `SDWAN_USERNAME` is for vManage API, `IOSXE_USERNAME` is for device SSH).

---

*Document Version: 1.0*
*Date: December 2024*
*Status: DRAFT - Ready for review*
