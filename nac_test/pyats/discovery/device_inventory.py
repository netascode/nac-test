# -*- coding: utf-8 -*-

"""Device inventory discovery for SSH-based tests.

This module handles discovering device inventory from test architectures
in an architecture-agnostic way using the contract pattern.
"""

from pathlib import Path
from typing import List, Dict, Any
import logging
import yaml
import sys
import importlib.util

logger = logging.getLogger(__name__)


class DeviceInventoryDiscovery:
    """Handles device inventory discovery from test architectures."""

    def __init__(self, output_dir: Path, merged_data_filename: str):
        """Initialize device inventory discovery.

        Args:
            output_dir: Directory containing merged data model
            merged_data_filename: Name of the merged data model file
        """
        self.output_dir = Path(output_dir)
        self.merged_data_filename = merged_data_filename

    def get_device_inventory(self, test_files: List[Path]) -> List[Dict[str, Any]]:
        """Get device inventory from test architecture in an architecture-agnostic way.

        This method implements the contract pattern for SSH-based test architectures.
        It dynamically discovers which devices to test without knowing anything about
        the specific architecture (SD-WAN, NXOS, IOSXE, etc.).

        How it works:
        1. Takes D2D test files (already filtered to only contain tests from /d2d/ directory)
        2. Imports the first test file to find the SSH base class
        3. Calls the base class's get_ssh_device_inventory() method
        4. Returns whatever the architecture provides - no modifications

        Why we should only need the first test file:
        - All D2D tests within an architecture are likely to share the same SSH base class
        - E.g., all SD-WAN D2D tests inherit from SDWANTestBase
        - E.g., future NXOS D2D tests would inherit from NXOSTestBase
        - So any D2D test file gives us access to the inventory method

        Architecture "contract":
        Every SSH-based test architecture MUST provide a base class that:
        - Inherits from SSHTestBase (provided by nac-test)
        - Implements get_ssh_device_inventory(data_model) class method
        - Returns a list of dicts with REQUIRED fields: hostname, host, os, username, password
        - Optional fields: type, platform (for PyATS/Unicon compatibility)
        #TODO: Prob need to think about "type" and "platform" b/c PyATS/Unicon is picky.

        Example implementations:
        - nac-sdwan: SDWANTestBase parses test_inventory.yaml + sites data
        - future nac-nxos: NXOSTestBase might parse a different YAML structure
        - future nac-iosxe: IOSXETestBase might scan JSON files in data/devices/

        The orchestrator doesn't care HOW each architecture finds its devices,
        it just calls the contract method and uses what it gets back.

        Args:
            test_files: List of D2D test files (we'll use the first one)

        Returns:
            List of device dictionaries with connection information
        """
        if not test_files:
            logger.error("No test files provided for device inventory discovery")
            return []

        # Load merged data model that contains device information
        # Each architecture decides how to parse this data model
        merged_data_path = self.output_dir / self.merged_data_filename

        if not merged_data_path.exists():
            logger.error(f"Merged data model not found at {merged_data_path}")
            return []

        with open(merged_data_path, "r") as f:
            data_model = yaml.safe_load(f)

        # Import the first D2D test file - all D2D tests in an architecture share the same SSH base class
        # For SD-WAN: all tests under /d2d/ inherit from SDWANTestBase
        # For future NXOS: all tests under /d2d/ would inherit from NXOSTestBase
        test_file = test_files[0]
        try:
            # I dont love this but we need to clean sys.argv before 
            # importing to prevent PyATS argument parser conflict
            # PyATS configuration module parses sys.argv at import time looking for --pyats-configuration
            # Our --pyats flag gets interpreted as an incomplete --pyats-configuration argument
            # This follows the same pattern as PyATS's own aetest module
            original_argv = sys.argv.copy()
            try:
                # Remove --pyats from argv temporarily
                sys.argv = [arg for arg in sys.argv if arg != "--pyats"]

                # Here we need to set up sys.path to enable test module imports
                # D2D test files contain imports like "from tests.pyats_common.base import ..."
                # but Python doesn't know where to find the 'tests' package when `nac-test` is run.
                # 
                # In the API test flow, the orchestrator sets up PYTHONPATH before discovery,
                # but for D2D tests, DeviceInventoryDiscovery runs BEFORE any path setup.
                # So we get into a bit of a pickle.
                # We need to handle this here to maintain the architecture-agnostic contract.
                #
                # How this works:
                # 1. Find the 'tests' directory in the test file's path hierarchy
                # 2. Add its parent directory to sys.path
                # 3. This allows Python to resolve "from tests.something import ..."
                #
                # Example:
                # - Test file: /home/user/nac-sdwan-terraform/tests/d2d/bgp_peers.py
                # - Find 'tests' dir: /home/user/nac-sdwan-terraform/tests
                # - Add to sys.path: /home/user/nac-sdwan-terraform
                # - Now "from tests.pyats_common..." resolves correctly
                test_dir = None
                for parent in test_file.parents:
                    if parent.name == 'tests':
                        test_dir = parent
                        break
                
                if test_dir:
                    # Add the parent of 'tests' directory to sys.path
                    test_parent = test_dir.parent
                    if str(test_parent) not in sys.path:
                        logger.debug(f"Adding {test_parent} to sys.path for test imports")
                        sys.path.insert(0, str(test_parent))
                else:
                    # Log a warning but continue - the test might not follow the expected structure
                    logger.warning(f"Could not find 'tests' directory in path of {test_file}")

                # Dynamically import the test module
                spec = importlib.util.spec_from_file_location(
                    "test_module", str(test_file)
                )
                if spec is None or spec.loader is None:
                    logger.error(f"Could not load test module from {test_file}")
                    return []

                module = importlib.util.module_from_spec(spec)
                sys.modules["test_module"] = module
                spec.loader.exec_module(module)

            finally:
                # Always restore original argv
                sys.argv = original_argv

            # Look for a class with get_ssh_device_inventory method
            # We check all classes in the module and their inheritance chain (MRO)
            for name, obj in vars(module).items():
                if hasattr(obj, "__mro__"):  # It's a class
                    # Check if this class or its parents have the method
                    # This handles inheritance: TestClass -> SDWANTestBase -> SSHTestBase
                    for cls in obj.__mro__:
                        if hasattr(cls, "get_ssh_device_inventory"):
                            # Found it! Call the method and return whatever it gives us
                            # The architecture handles all specifics: parsing files, resolving IPs, adding credentials

                            logger.info(
                                f"Found device inventory method in {cls.__name__}"
                            )
                            devices = cls.get_ssh_device_inventory(data_model)

                            return devices

        except Exception as e:
            logger.error(f"Failed to get device inventory from {test_file}: {e}")

        # This should never happen if the architecture follows the contract btw

        logger.error("No test class with get_ssh_device_inventory() method found")
        return []
