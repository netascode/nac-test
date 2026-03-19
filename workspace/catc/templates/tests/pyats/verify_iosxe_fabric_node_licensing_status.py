# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify Fabric Node Licensing Status
-------------------------------------------
This job verifies that all required licenses for SDA fabric operation are present and valid on IOS-XE devices.
It ensures both 'network-advantage' and 'dna-advantage' licenses are installed, in-use, and unrestricted.
"""

import time
import re
from pyats import aetest
import jmespath
from nac_test_pyats_common.iosxe import IOSXETestBase
from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify SDA Fabric Node Licensing Status"

DESCRIPTION = """This test ensures that all required SDA (Software-Defined Access) fabric node licenses are present and active on the device.
Specifically, it validates the existence, status, and attributes of 'network-advantage' and 'dna-advantage' licenses, which are essential for proper fabric operation. 
Verifying license presence and validity prevents feature restrictions, ensures compliance, and supports seamless SDA provisioning and automation."""

SETUP = (
    "* SSH access to the IOS-XE network device is available.\n"
    "* Authentication credentials are valid and configured on the device.\n"
    "* Device is registered for smart licensing and has internet connectivity if required.\n"
    "* The device is deployed as part of an SDA fabric or expected to support SDA features.\n"
)

PROCEDURE = (
    "* Establish SSH connection to the target network device.\n"
    "* Execute the CLI command: *show license all*.\n"
    "* Parse the output using the Genie parser if available, or fall back to regex parsing if necessary.\n"
    "* For EACH discovered license item (from parsed output or regex):\n"
    "    * Identify all licenses where the name matches 'network-advantage' or 'dna-advantage' (case-insensitive, spaces or dashes allowed).\n"
    "    * Extract and record the following attributes:\n"
    "        * License name\n"
    "        * License type (Perpetual or Subscription)\n"
    "        * Status (IN USE/NOT IN USE)\n"
    "        * Count\n"
    "        * Enforcement type\n"
    "        * Export status\n"
    "* For each license type ('network-advantage' and 'dna-advantage'), verify the following:\n"
    "    * Status is 'IN USE'\n"
    "    * License type: 'network-advantage' must be 'Perpetual'; 'dna-advantage' can be 'Perpetual' or 'Subscription'\n"
    "    * Count is greater than or equal to 1\n"
    "    * Export status is 'NOT RESTRICTED'\n"
    "* Summarize results and report any missing, unhealthy, or incorrectly attributed licenses."
)

PASS_FAIL_CRITERIA = (
    "**This test passes when all of the following conditions are met:**\n"
    "\n"
    "* At least one 'network-advantage' license is present with:\n"
    "    * Status 'IN USE'\n"
    "    * License type 'Perpetual'\n"
    "    * Count >= 1\n"
    "    * Export status 'NOT RESTRICTED'\n"
    "* At least one 'dna-advantage' license is present with:\n"
    "    * Status 'IN USE'\n"
    "    * License type 'Perpetual' or 'Subscription'\n"
    "    * Count >= 1\n"
    "    * Export status 'NOT RESTRICTED'\n"
    "* CLI command output is successfully parsed (either Genie or regex) and all license checks are performed without error.\n"
    "\n"
    "**This test fails if any of the following criteria are met:**\n"
    "\n"
    "* No 'network-advantage' or 'dna-advantage' license is discovered in the device output.\n"
    "* Either license is present but does not have status 'IN USE'.\n"
    "* 'network-advantage' license type is not 'Perpetual'.\n"
    "* 'dna-advantage' license type is not 'Perpetual' or 'Subscription'.\n"
    "* Count < 1 for either license.\n"
    "* Export status is not 'NOT RESTRICTED' for either license.\n"
    "* CLI command execution or parsing fails, or no license information can be extracted.\n"
)


import re


class VerifyFabricNodeLicensingStatus(IOSXETestBase):
    """
    [IOS-XE] Verify Fabric Node Licensing Status

    Verifies that SDA fabric node has appropriate 'network-advantage' and 'dna-advantage' licenses
    with correct status, type, count, and export status using 'show license all'.
    """

    TEST_CONFIG = {
        "resource_type": "SDA Fabric Node Licensing",
        "api_endpoint": "show license all",
        "expected_values": {
            # These are the attributes to verify per pass/fail criteria.
            # The checks will be keyed by license_name (for regex) or feature_name (for Genie).
            # See verify_item for detailed matching logic (since criteria are per license type).
            # All keys below are extracted exactly as they appear in Genie/regex output.
            # We will check both 'network-advantage' and 'dna-advantage' licenses.
            # Values are "meta" - used for logic, not for direct comparison.
            "license_name": "<meta>",  # regex
            "feature_name": "<meta>",  # Genie
            "status": "IN USE",
            "license_type": [
                "Perpetual",
                "Subscription",
            ],  # dna-advantage can be either
            "count": 1,
            "export_status": "NOT RESTRICTED",
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_licenses",
            "healthy_licenses",
            "unhealthy_licenses",
        ],
    }

    @aetest.test
    def test_fabric_node_licensing_status(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """
        Returns a single context to trigger global SDA fabric node licensing check.
        """
        return [
            {
                "check_type": "fabric_node_licensing_status",
                "verification_scope": "all_fabric_node_licenses",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification: Ensure SDA fabric node has required 'network-advantage' and 'dna-advantage' licenses
        with correct status/type/count/export_status.

        Handles both Genie-parsed and regex-parsed output.
        """
        async with semaphore:
            try:
                command = self.TEST_CONFIG["api_endpoint"]

                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"],
                    "All Fabric Node Licenses",
                    check_type=context.get("check_type"),
                    verification_scope=context.get("verification_scope"),
                )

                start_time = time.time()

                with self.test_context(api_context):
                    output = await self.execute_command(command)
                command_duration = time.time() - start_time

                parse_start = time.time()
                # Use correct parsing: if regex, handle here. Otherwise, use parse_output.
                is_regex = False

                # Regex pattern to match license blocks in 'show license all' output.
                # The actual device output format is:
                #   <License Header>:
                #     Description: ...
                #     Count: ...
                #     Version: ...
                #     Status: IN USE|NOT IN USE
                #     Export status: NOT RESTRICTED|RESTRICTED
                #     Feature Name: network-advantage|dna-advantage|...
                #     Feature Description: ...
                #     Enforcement type: ENFORCED|NOT ENFORCED
                #     License type: Perpetual|Subscription
                #
                # We use a flexible pattern that matches blocks containing Feature Name
                # for network-advantage or dna-advantage (case-insensitive, with dash or space).
                regex_pattern = (
                    r"(?P<header>[^\n]+):\s*[\r\n]+"
                    r"\s*Description:\s*(?P<description>[^\r\n]*)\s*[\r\n]+"
                    r"\s*Count:\s*(?P<count>\d+)\s*[\r\n]+"
                    r"\s*Version:\s*(?P<version>[^\r\n]*)\s*[\r\n]+"
                    r"\s*Status:\s*(?P<status>IN USE|NOT IN USE)\s*[\r\n]+"
                    r"\s*Export status:\s*(?P<export_status>NOT RESTRICTED|RESTRICTED)\s*[\r\n]+"
                    r"\s*Feature Name:\s*(?P<license_name>[^\r\n]+)\s*[\r\n]+"
                    r"\s*Feature Description:\s*(?P<feature_description>[^\r\n]*)\s*[\r\n]+"
                    r"\s*Enforcement type:\s*(?P<enforcement_type>ENFORCED|NOT ENFORCED)\s*[\r\n]+"
                    r"\s*License type:\s*(?P<license_type>Perpetual|Subscription)"
                )

                # Helper function to normalize and match license names
                # Matches: network-advantage, network advantage, dna-advantage, dna advantage
                # Also matches variants like: network-adv, dna-adv, essentials, etc.
                def normalize_license_name(name):
                    """Normalize license name for matching."""
                    if not name:
                        return None
                    name_lower = str(name).strip().lower().replace(" ", "-")
                    # Match network-advantage variants
                    if "network" in name_lower and "advantage" in name_lower:
                        return "network-advantage"
                    # Match dna-advantage variants
                    if "dna" in name_lower and "advantage" in name_lower:
                        return "dna-advantage"
                    return None

                # If parse_output returns None, try regex (for explicit regex parsing jobs)
                parsed_output = self.parse_output(command, output=output)
                # Try to detect if we're in the REGEX path based on the output type
                if parsed_output is None:
                    # Try regex parse per instructions
                    is_regex = True
                    matches = list(
                        re.finditer(
                            regex_pattern,
                            output,
                            re.MULTILINE | re.DOTALL | re.IGNORECASE,
                        )
                    )
                    licenses = []
                    for match in matches:
                        groupdict = match.groupdict()
                        # Normalize keys and types
                        license_name_raw = groupdict.get("license_name", "")
                        license_name = normalize_license_name(license_name_raw)
                        # Only 'network-advantage' and 'dna-advantage' are relevant
                        if license_name is None:
                            continue
                        # Normalize count to int
                        try:
                            groupdict["count"] = int(groupdict.get("count", "0"))
                        except Exception:
                            groupdict["count"] = 0
                        # Make all values explicit strings (except count)
                        for k, v in groupdict.items():
                            if k != "count":
                                groupdict[k] = str(v).strip()
                        groupdict["license_name"] = license_name
                        licenses.append(groupdict)
                    parsed_output = licenses  # List of dicts
                parse_duration = time.time() - parse_start

                api_duration = command_duration + parse_duration

                context["api_context"] = api_context

                if parsed_output is None:
                    context["display_context"] = "SDA Fabric Node Licensing -> State"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=f"Parsed output is None for command: {command}",
                        api_duration=api_duration,
                    )

                # Extract all license items for validation using JMESPath
                # Support both Genie and regex paths
                if is_regex:
                    # REGEX: parsed_output is a list of dicts (each license)
                    license_items = parsed_output
                else:
                    # GENIE: extract licenses from license_usage.license_name dict
                    # 'license_usage.license_name' is a dict of license blocks
                    license_dict = (
                        jmespath.search("license_usage.license_name", parsed_output)
                        or {}
                    )
                    license_items = []
                    for lic_key, lic_val in license_dict.items():
                        # We want only those licenses whose 'feature_name' matches network-advantage or dna-advantage
                        feature_name = jmespath.search("feature_name", lic_val)
                        normalized_name = normalize_license_name(feature_name)
                        if normalized_name is not None:
                            # Add the normalized feature_name field for matching
                            lic_val["feature_name"] = normalized_name
                            # Add the license_name as a field for logging (original key)
                            lic_val["license_name"] = lic_key.strip().lower()
                            license_items.append(lic_val)

                if not license_items:
                    context["display_context"] = "SDA Fabric Node Licensing -> State"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No relevant SDA fabric node licenses discovered.\n\n"
                            "This indicates that either:\n"
                            "• No 'network-advantage' or 'dna-advantage' licenses are present\n"
                            "• License information could not be parsed from the device\n"
                            "• Device is not properly licensed for SDA fabric features\n\n"
                            "Please verify device smart licensing registration and provisioning."
                        ),
                        api_duration=api_duration,
                    )

                # Pass/Fail logic:
                #   - At least ONE network-advantage (status IN USE, license_type Perpetual, count>=1, export_status NOT RESTRICTED)
                #   - At least ONE dna-advantage (status IN USE, license_type Perpetual/Subscription, count>=1, export_status NOT RESTRICTED)
                #   - If multiple, at least one must match each criteria.

                # Find all relevant licenses by type
                network_adv_licenses = []
                dna_adv_licenses = []

                for item in license_items:
                    # Determine feature type
                    if is_regex:
                        name = jmespath.search("license_name", item)
                    else:
                        name = jmespath.search("feature_name", item)
                    if name is None:
                        continue
                    name = str(name).strip().lower()
                    if name == "network-advantage":
                        network_adv_licenses.append(item)
                    elif name == "dna-advantage":
                        dna_adv_licenses.append(item)

                validation_results = []
                failures = []
                all_items_healthy = True
                healthy_count = 0
                unhealthy_count = 0
                total_licenses = len(network_adv_licenses) + len(dna_adv_licenses)

                # Helper for attribute extraction
                def extract_value(attribute_name, item):
                    val = jmespath.search(attribute_name, item)
                    if val is None:
                        return "Not Found"
                    elif val == "":
                        return "<empty>"
                    return val

                # --- Check network-advantage ---
                network_adv_found = False
                for lic in network_adv_licenses:
                    # All criteria must be met
                    item_failures = []
                    # status
                    status = extract_value("status", lic)
                    if str(status) != "IN USE":
                        item_failures.append(
                            f"  • status: Expected 'IN USE', got '{status}'"
                        )
                    # license_type
                    license_type = extract_value("license_type", lic)
                    if str(license_type) != "Perpetual":
                        item_failures.append(
                            f"  • license_type: Expected 'Perpetual', got '{license_type}'"
                        )
                    # count
                    count = extract_value("count", lic)
                    try:
                        count_int = int(count)
                    except Exception:
                        count_int = 0
                    if count_int < 1:
                        item_failures.append(f"  • count: Expected >= 1, got '{count}'")
                    # export_status
                    export_status = extract_value("export_status", lic)
                    if str(export_status) != "NOT RESTRICTED":
                        item_failures.append(
                            f"  • export_status: Expected 'NOT RESTRICTED', got '{export_status}'"
                        )

                    # For logging
                    log_identifier = (
                        f"license_type=network-advantage, "
                        f"description={extract_value('description', lic)}, "
                        f"status={status}, license_type={license_type}, count={count}, export_status={export_status}"
                    )

                    if not item_failures:
                        validation_results.append(f"✅ {log_identifier}")
                        healthy_count += 1
                        network_adv_found = True
                    else:
                        validation_results.append(
                            f"❌ {log_identifier} -- " + " | ".join(item_failures)
                        )
                        failures.append(
                            f"**network-advantage license**\n{chr(10).join(item_failures)}"
                        )
                        unhealthy_count += 1
                        all_items_healthy = False

                # If no network-advantage license was healthy
                if not network_adv_found:
                    all_items_healthy = False
                    failures.append(
                        f"**network-advantage license**\n  • Not found or did not meet all criteria!"
                    )

                # --- Check dna-advantage ---
                dna_adv_found = False
                for lic in dna_adv_licenses:
                    item_failures = []
                    # status
                    status = extract_value("status", lic)
                    if str(status) != "IN USE":
                        item_failures.append(
                            f"  • status: Expected 'IN USE', got '{status}'"
                        )
                    # license_type
                    license_type = extract_value("license_type", lic)
                    if str(license_type) not in ("Perpetual", "Subscription"):
                        item_failures.append(
                            f"  • license_type: Expected 'Perpetual' or 'Subscription', got '{license_type}'"
                        )
                    # count
                    count = extract_value("count", lic)
                    try:
                        count_int = int(count)
                    except Exception:
                        count_int = 0
                    if count_int < 1:
                        item_failures.append(f"  • count: Expected >= 1, got '{count}'")
                    # export_status
                    export_status = extract_value("export_status", lic)
                    if str(export_status) != "NOT RESTRICTED":
                        item_failures.append(
                            f"  • export_status: Expected 'NOT RESTRICTED', got '{export_status}'"
                        )

                    log_identifier = (
                        f"license_type=dna-advantage, "
                        f"description={extract_value('description', lic)}, "
                        f"status={status}, license_type={license_type}, count={count}, export_status={export_status}"
                    )

                    if not item_failures:
                        validation_results.append(f"✅ {log_identifier}")
                        healthy_count += 1
                        dna_adv_found = True
                    else:
                        validation_results.append(
                            f"❌ {log_identifier} -- " + " | ".join(item_failures)
                        )
                        failures.append(
                            f"**dna-advantage license**\n{chr(10).join(item_failures)}"
                        )
                        unhealthy_count += 1
                        all_items_healthy = False

                if not dna_adv_found:
                    all_items_healthy = False
                    failures.append(
                        f"**dna-advantage license**\n  • Not found or did not meet all criteria!"
                    )

                # Update context metrics
                context["total_licenses"] = total_licenses
                context["healthy_licenses"] = healthy_count
                context["unhealthy_licenses"] = unhealthy_count

                result_summary = "\n".join(validation_results)

                if all_items_healthy and network_adv_found and dna_adv_found:
                    context["display_context"] = "SDA Fabric Node Licensing -> State"
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**SDA Fabric Node Licensing Check PASSED**\n\n"
                            f"All required licenses ('network-advantage' and 'dna-advantage') are present with correct status, type, count, and export status.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**License Status:**\n"
                            f"• Total discovered relevant licenses: {total_licenses}\n"
                            f"• Healthy licenses: {healthy_count}\n"
                            f"• Unhealthy licenses: {unhealthy_count}\n"
                            f"• Both required license types present and valid: Yes\n"
                            f"• Command execution duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    context["display_context"] = "SDA Fabric Node Licensing -> State"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**SDA Fabric Node Licensing Check FAILED**\n\n"
                            f"One or more required licenses ('network-advantage' and/or 'dna-advantage') are missing or do not meet status/type/count/export status requirements.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Detailed Failures:**\n"
                            f"{chr(10).join(failures)}\n\n"
                            f"**License Status:**\n"
                            f"• Total discovered relevant licenses: {total_licenses}\n"
                            f"• Healthy licenses: {healthy_count}\n"
                            f"• Unhealthy licenses: {unhealthy_count}\n"
                            f"• Both required license types present and valid: {'Yes' if (network_adv_found and dna_adv_found) else 'No'}\n\n"
                            f"**Please verify:**\n"
                            f"• Smart licensing registration and connectivity\n"
                            f"• That 'network-advantage' and 'dna-advantage' licenses are installed and in-use\n"
                            f"• That license types are correct (Perpetual/Subscription as required)\n"
                            f"• That license count is >= 1 for both\n"
                            f"• That export status is 'NOT RESTRICTED'\n"
                            f"• Review device licensing portal for further details\n"
                            f"• Command execution duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = (
                    f"Exception during SDA Fabric Node Licensing check: {str(e)}"
                )
                self.logger.error(
                    f"Exception for SDA Fabric Node Licensing Check: {error_msg}",
                    exc_info=True,
                )
                context["display_context"] = "SDA Fabric Node Licensing -> State"
                reason = (
                    f"PyATS Framework Exception: {error_msg}\n\n"
                    f"This is a PyATS code issue, not an issue with your data model, "
                    f"Catalyst Center configuration, or your network devices.\n\n"
                    f"Please contact Cisco TAC for support with this error."
                )
                return self.format_verification_result(
                    status=ResultStatus.FAILED,
                    context=context,
                    reason=reason,
                    api_duration=0,
                )
