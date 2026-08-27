# PyATS Test Case Quickstart

## What is this?

The nac-test framework can run pyATS test cases alongside Robot Framework tests. PyATS tests are pure Python classes that verify network state against expected values from a data model or static expectations. Tests are auto-discovered via AST analysis—just inherit from the appropriate base class and place your file in the test directory. This guide gets you writing tests in 5 minutes.

## Prerequisites

- **nac-test** >= 2.0
- **nac-test-pyats-common** (install via `pip install nac-test-pyats-common`)
- **pyATS** (installed as a dependency)

Import the base class for your platform:

- **ACI:** `from nac_test_pyats_common.aci import APICTestBase`
- **SD-WAN Manager:** `from nac_test_pyats_common.sdwan import SDWANManagerTestBase`
- **Catalyst Center:** `from nac_test_pyats_common.catc import CatalystCenterTestBase`
- **IOS-XE SSH:** `from nac_test_pyats_common.iosxe import IOSXETestBase`

## Minimal API Test Example

This complete SD-WAN Manager test verifies BGP neighbor sessions are established:

```python
"""Verify SD-WAN BGP neighbor sessions are established."""

import asyncio
import logging
import time
from typing import Any

from pyats import aetest
from nac_test_pyats_common.sdwan.api_test_base import SDWANManagerTestBase
from nac_test.pyats_core.reporting.types import ResultStatus

logger = logging.getLogger(__name__)

TITLE = "Verify SD-WAN BGP Neighbor State"
DESCRIPTION = """Validates that all BGP neighbor sessions are in 'established' state."""
SETUP = "* Access to SD-WAN Manager via HTTPS API.\n* Valid credentials configured.\n"
PROCEDURE = "* Query BGP neighbors per device.\n* Verify state is 'established'.\n"
PASS_FAIL_CRITERIA = "* PASS: All neighbors established.\n* FAIL: Any neighbor not established.\n* SKIP: No neighbors found.\n"


class VerifyBGPNeighbors(SDWANManagerTestBase):
    """Verify BGP neighbor sessions are established."""

    TEST_CONFIG = {
        "resource_type": "SD-WAN BGP Neighbors",
        "api_endpoint": "/dataservice/device/bgp/neighbors",
        "identifier_format": "Device {hostname} ({system_ip})",
        "log_fields": ["hostname", "system_ip"],
    }

    @aetest.test
    def test_bgp_neighbors(self, steps):
        """Entry point — delegates to async verification."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self) -> list[dict[str, Any]]:
        """Extract devices from data model."""
        devices = self.get_devices_from_data_model()
        return [
            {"system_ip": d["system_ip"], "hostname": d.get("hostname", d["system_ip"])}
            for d in devices
        ]

    async def verify_item(
        self, semaphore: asyncio.Semaphore, client: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Verify BGP neighbors for one device."""
        async with semaphore:
            system_ip = context["system_ip"]
            hostname = context["hostname"]
            api_context = self.build_api_context(
                self.TEST_CONFIG["resource_type"],
                f"Device {hostname} ({system_ip})",
            )
            start_time = time.time()
            response = await client.get(
                f"{self.TEST_CONFIG['api_endpoint']}?deviceId={system_ip}",
                test_context=api_context,
            )
            api_duration = time.time() - start_time
            context["display_context"] = f"BGP -> {hostname} ({system_ip})"

            data = response.json().get("data", [])
            if not data:
                return self.format_verification_result(
                    status=ResultStatus.SKIPPED, context=context,
                    reason=f"No BGP neighbors for {hostname}", api_duration=api_duration,
                )

            failed = [n for n in data if n.get("state") != "established"]
            if failed:
                return self.format_verification_result(
                    status=ResultStatus.FAILED, context=context,
                    reason=f"{len(failed)}/{len(data)} BGP neighbors not established on {hostname}",
                    api_duration=api_duration,
                )

            return self.format_verification_result(
                status=ResultStatus.PASSED, context=context,
                reason=f"All {len(data)} BGP neighbors established on {hostname}",
                api_duration=api_duration,
            )
```

## Minimal SSH/Device-to-Device Test Example

This IOS-XE test skeleton shows how to execute commands and parse output:

```python
"""Verify OSPF neighbors are in Full state."""

import asyncio
import logging
import time
from typing import Any

from pyats import aetest
from nac_test_pyats_common.iosxe.test_base import IOSXETestBase
from nac_test.pyats_core.reporting.types import ResultStatus

logger = logging.getLogger(__name__)

TITLE = "Verify OSPF Neighbor State"
DESCRIPTION = """Validates OSPF neighbors are in Full state on IOS-XE devices."""
SETUP = "* SSH access to IOS-XE devices.\n"
PROCEDURE = "* Execute 'show ip ospf neighbor' and parse output.\n* Verify all neighbors are Full.\n"
PASS_FAIL_CRITERIA = "* PASS: All neighbors Full.\n* FAIL: Any neighbor not Full.\n"


class VerifyOSPFNeighborState(IOSXETestBase):
    """Verify OSPF neighbors on an IOS-XE device."""

    TEST_CONFIG = {
        "resource_type": "OSPF Neighbors",
        "api_endpoint": "show ip ospf neighbor",
        "identifier_format": "Device {hostname}",
        "log_fields": ["hostname"],
    }

    @aetest.test
    def test_ospf_neighbors(self, steps):
        self.run_async_verification_test(steps)

    def get_items_to_verify(self) -> list[dict[str, Any]]:
        return [{"hostname": self.hostname}]

    async def verify_item(
        self, semaphore: asyncio.Semaphore, client: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        async with semaphore:
            command = self.TEST_CONFIG["api_endpoint"]
            api_context = self.build_api_context(
                self.TEST_CONFIG["resource_type"], self.hostname,
            )
            with self.test_context(api_context):
                output = await self.execute_command(command)
            # nac-test 2.0: parse_output is sync
            # nac-test 2.1+: use await self.parse_output(command, output=output)
            parsed = self.parse_output(command, output=output)

            context["display_context"] = f"OSPF -> {self.hostname}"
            if not parsed:
                return self.format_verification_result(
                    status=ResultStatus.SKIPPED, context=context,
                    reason=f"No OSPF output parsed on {self.hostname}",
                    api_duration=0,
                )
            # ... verify parsed data ...
            return self.format_verification_result(
                status=ResultStatus.PASSED, context=context,
                reason=f"All OSPF neighbors Full on {self.hostname}",
                api_duration=0,
            )
```

## How to Run

Run your tests with the `--pyats` flag to skip Robot Framework tests for faster iteration:

```bash
export SDWAN_URL=...
export SDWAN_USERNAME=...
read -s SDWAN_PASSWORD
export SDWAN_PASSWORD
nac-test --pyats \
  -t path/to/tests/ \
  -d data.yaml \
  -o results/
```

Test results are written to the `results/` directory with HTML reports for easy review.

## The 3-Method Contract

Every pyATS test in this framework implements three things:

1. An `@aetest.test` method that calls `self.run_async_verification_test(steps)`
2. `get_items_to_verify()` returning a list of context dictionaries (one per item to verify)
3. `async verify_item()` that verifies one item and returns `self.format_verification_result()`

This pattern enables parallel verification, consistent reporting, and automatic HTML report generation.

## Module-Level Constants (Strongly Recommended)

The module-level constants (`TITLE`, `DESCRIPTION`, `SETUP`, `PROCEDURE`, `PASS_FAIL_CRITERIA`) are strongly recommended as they generate rich HTML reports with test documentation. While not strictly required, they significantly improve test readability and maintainability.

## Next Steps

- **Full Developer Guide:** See [test-case-guide.md](test-case-guide.md) for detailed patterns, error handling, and advanced features
- **API Reference:** See [api-reference.md](api-reference.md) for complete method signatures and base class capabilities
- **Runnable Examples:** See `workspace/doc-examples/` for complete working tests you can run locally with `./run_examples.sh`
