# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
[NRFU]: Verify No Critical Errors in System Logs
------------------------------------------------
This job verifies that the IOS-XE device system log contains no critical errors,
hardware failures, configuration rollbacks, AAA failures, or software exceptions.
"""

import time
import re
from pyats import aetest

import jmespath
from nac_test_pyats_common.iosxe import IOSXETestBase
from nac_test.pyats_core.reporting.types import ResultStatus

TITLE = "Verify No Critical Errors in System Logs"

DESCRIPTION = """This test checks the system log on an IOS-XE device for the presence of any
critical errors, hardware failures, configuration rollbacks, AAA failures, software exceptions,
or recurring error-level messages. System logs are essential for identifying operational issues,
hardware faults, authentication problems, or abnormal software behavior. Ensuring that the
system log is free of high-severity or persistent errors is vital for network reliability,
device stability, and early detection of infrastructure issues."""

SETUP = (
    "* SSH access to the target IOS-XE network device is available.\n"
    "* Authentication credentials for the device are valid and configured.\n"
    "* System logging is enabled and log buffer contains current entries.\n"
    "* The device is operational and reachable via the management network.\n"
)

PROCEDURE = (
    "* Establish SSH connection to the IOS-XE network device.\n"
    "* Execute the CLI command: *show logging* to retrieve the device system log buffer.\n"
    "* Parse the command output using the Genie parser to obtain structured log entries.\n"
    "* For EACH log entry discovered in the parsed output:\n"
    "    * Extract the log message severity from the syslog header (e.g., %FAC-SEV-CODE).\n"
    "    * Check for the following:\n"
    "        * Any log entry with severity 0 (Emergency), 1 (Alert), or 2 (Critical).\n"
    "        * Any message text indicating hardware failures (e.g., power, fan, module).\n"
    "        * Any message text indicating configuration rollback or abort.\n"
    "        * Any message text indicating AAA (authentication/authorization/accounting) failure.\n"
    "        * Any message text indicating a software exception or crash.\n"
    "        * Recurring (persistent) severity 3 (Error) messages by counting repeated signatures.\n"
    "* Summarize results, reporting any discovered critical or recurring issues.\n"
)

PASS_FAIL_CRITERIA = (
    "**This test passes when all of the following conditions are met:**\n"
    "\n"
    "* At least one log entry is discovered in the system log buffer.\n"
    "* No log entries have severity 0, 1, or 2 (Emergency, Alert, Critical).\n"
    "* No log entries indicate hardware failures (e.g., FAN, PSU, module, overheat, sensor).\n"
    "* No log entries indicate configuration rollback or abort events.\n"
    "* No log entries indicate AAA (authentication/authorization/accounting) failures.\n"
    "* No log entries indicate software exceptions or crashes.\n"
    "* No recurring (persistent) severity 3 (Error) messages with the same signature.\n"
    "\n"
    "**This test fails if any of the following criteria are met:**\n"
    "\n"
    "* The system log buffer is empty or cannot be parsed.\n"
    "* One or more log entries have severity 0, 1, or 2 (Emergency, Alert, Critical).\n"
    "* Any log entry indicates hardware failure, configuration rollback, AAA failure, or software exception.\n"
    "* One or more recurring severity 3 (Error) messages are found with the same signature.\n"
    "* The CLI command fails to execute or returns an error.\n"
    "* The Genie parser fails to parse the command output.\n"
)



class VerifyNoCriticalErrorsInSystemLogs(IOSXETestBase):
    """
    [IOS-XE] Verify No Critical Errors in System Logs

    Checks all log entries in 'logs' (from Genie-parsed 'show logging') for:
    - No critical syslog messages (severity 0, 1, or 2)
    - No log messages indicating hardware failures, configuration rollbacks, AAA failures, or software exceptions
    - No persistent or recurring issues at severity 3 (Error)
    """

    TEST_CONFIG = {
        "resource_type": "System Log",
        "api_endpoint": "show logging",
        "expected_values": {
            # There are no direct keys for severity/message in Genie output;
            # We must parse 'logs' entries for syslog severity and error patterns.
            "logs": "no_critical_errors",  # Special marker; actual logic is in verify_item
        },
        "log_fields": [
            "check_type",
            "verification_scope",
            "total_logs",
            "critical_logs",
            "hardware_error_logs",
            "config_rollback_logs",
            "aaa_failure_logs",
            "sw_exception_logs",
            "persistent_error_logs",
        ],
    }

    @aetest.test
    def test_system_log_health(self, steps):
        """Entry point - delegates to base class orchestration."""
        self.run_async_verification_test(steps)

    def get_items_to_verify(self):
        """
        Returns a single context to trigger the log buffer check.
        """
        return [
            {
                "check_type": "system_log_health",
                "verification_scope": "all_syslog_entries",
            }
        ]

    async def verify_item(self, semaphore, client, context):
        """
        Verification: Check all logs in Genie-parsed 'show logging' output for:
        - No severity 0, 1, 2 log entries
        - No messages indicating hardware failure, config rollback, AAA failure, software exception
        - No persistent/recurrent severity 3 errors
        """
        async with semaphore:
            try:
                command = self.TEST_CONFIG["api_endpoint"]

                api_context = self.build_api_context(
                    self.TEST_CONFIG["resource_type"],
                    "All System Logs",
                    check_type=context.get("check_type"),
                    verification_scope=context.get("verification_scope"),
                )

                start_time = time.time()

                with self.test_context(api_context):
                    output = await self.execute_command(command)
                command_duration = time.time() - start_time

                parse_start = time.time()
                parsed_output = self.parse_output(command, output=output)
                parse_duration = time.time() - parse_start

                api_duration = command_duration + parse_duration

                context["api_context"] = api_context

                if parsed_output is None:
                    context['display_context'] = "System Log -> State"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=f"Parsed output is None for command: {command}",
                        api_duration=api_duration,
                    )

                # Extract all logs (list of log lines)
                log_lines = jmespath.search("logs[]", parsed_output) or []
                total_logs = len(log_lines)
                context["total_logs"] = total_logs

                if not log_lines:
                    context['display_context'] = "System Log -> State"
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            "No log entries found in Genie-parsed 'show logging' output.\n\n"
                            "This indicates that either:\n"
                            "• The device logging buffer is empty\n"
                            "• The parser failed to extract logs\n"
                            "• There are no recent log messages\n\n"
                            "Please verify device logging configuration and try again."
                        ),
                        api_duration=api_duration,
                    )

                # Severity mapping: %FAC-SEV-CODE
                # 0 = Emergency, 1 = Alert, 2 = Critical, 3 = Error, 4 = Warning, 5 = Notification, 6 = Informational, 7 = Debug
                severity_regex = re.compile(r"%[\w\-]+-(\d)-[\w_]+:")

                # Patterns for hardware failure, config rollback, AAA failure, software exceptions
                hw_pattern = re.compile(
                    r"(FAN|PSU|PWR|SUPERVISOR|HARDWARE|OVERHEAT|TEMP|FRU|SENSOR|ASIC|linecard|module|hardware failure|power failure|voltage|fan fail|system overheat)",
                    re.IGNORECASE,
                )
                config_rb_pattern = re.compile(
                    r"(rollback|config(uration)?\s+rollback|rollback completed|rollback failed|rollback triggered|config replace|config failure|config error|config abort)",
                    re.IGNORECASE,
                )
                aaa_fail_pattern = re.compile(
                    r"(AAA|authentication|authorization|accounting)\s+(fail|failure|error|denied|unsuccessful|unsuccessfully|rejected|invalid)|login failed|user authentication failed",
                    re.IGNORECASE,
                )
                sw_exc_pattern = re.compile(
                    r"(exception|crash|software error|fatal error|stack trace|core dumped|segmentation fault|SW crash|SW exception)",
                    re.IGNORECASE,
                )

                # For persistent/recurrent errors at severity 3, collect count by message signature
                error_sig_counter = {}

                critical_logs = []
                hardware_error_logs = []
                config_rollback_logs = []
                aaa_failure_logs = []
                sw_exception_logs = []
                error_logs = []

                validation_results = []
                failures = []

                for log in log_lines:
                    # Try to extract severity
                    sev_match = severity_regex.search(log)
                    if sev_match:
                        severity = int(sev_match.group(1))
                    else:
                        # If no severity, treat as informational (best effort, usually banner lines or incomplete)
                        severity = 6

                    # Check for severity 0/1/2 (emerg/alert/critical)
                    if severity in (0, 1, 2):
                        critical_logs.append(log)
                        validation_results.append(
                            f"❌ [Severity {severity}] {log.strip()}"
                        )

                    # Check for hardware failures (any severity)
                    if hw_pattern.search(log):
                        hardware_error_logs.append(log)

                    # Check for config rollback (any severity)
                    if config_rb_pattern.search(log):
                        config_rollback_logs.append(log)

                    # Check for AAA failures (any severity)
                    if aaa_fail_pattern.search(log):
                        aaa_failure_logs.append(log)

                    # Check for SW exceptions (any severity)
                    if sw_exc_pattern.search(log):
                        sw_exception_logs.append(log)

                    # Track severity 3 (Error) for persistent errors
                    if severity == 3:
                        # Build an error signature (facility, code, message w/o timestamp)
                        err_sig_match = re.search(r"%([\w\-]+)-3-([\w_]+):\s*(.+)", log)
                        if err_sig_match:
                            sig = f"{err_sig_match.group(1)}-{err_sig_match.group(2)}: {err_sig_match.group(3).strip()}"
                            # Remove any interface, address, or time-variant info to generalize signature
                            sig = re.sub(r"(\d+\.\d+\.\d+\.\d+)|(\bGi\d+/\d+/\d+\b)|(\bTe\d+/\d+/\d+\b)|(\bEth\d+/\d+/\d+\b)", "<REDACTED>", sig)
                        else:
                            sig = log
                        error_sig_counter[sig] = error_sig_counter.get(sig, 0) + 1
                        error_logs.append(log)

                # Persistent error = same error signature seen more than once
                persistent_error_logs = [
                    sig for sig, count in error_sig_counter.items() if count > 1
                ]

                context["critical_logs"] = len(critical_logs)
                context["hardware_error_logs"] = len(hardware_error_logs)
                context["config_rollback_logs"] = len(config_rollback_logs)
                context["aaa_failure_logs"] = len(aaa_failure_logs)
                context["sw_exception_logs"] = len(sw_exception_logs)
                context["persistent_error_logs"] = len(persistent_error_logs)

                # Build failures for all categories found
                if critical_logs:
                    failures.append(
                        f"**Critical severity logs (0/1/2) found ({len(critical_logs)}):**\n"
                        + "\n".join(f"  • {l}" for l in critical_logs[:5])
                        + ("\n  ... (additional omitted)" if len(critical_logs) > 5 else "")
                    )
                if hardware_error_logs:
                    failures.append(
                        f"**Hardware failure logs found ({len(hardware_error_logs)}):**\n"
                        + "\n".join(f"  • {l}" for l in hardware_error_logs[:5])
                        + ("\n  ... (additional omitted)" if len(hardware_error_logs) > 5 else "")
                    )
                if config_rollback_logs:
                    failures.append(
                        f"**Configuration rollback logs found ({len(config_rollback_logs)}):**\n"
                        + "\n".join(f"  • {l}" for l in config_rollback_logs[:5])
                        + ("\n  ... (additional omitted)" if len(config_rollback_logs) > 5 else "")
                    )
                if aaa_failure_logs:
                    failures.append(
                        f"**AAA failure logs found ({len(aaa_failure_logs)}):**\n"
                        + "\n".join(f"  • {l}" for l in aaa_failure_logs[:5])
                        + ("\n  ... (additional omitted)" if len(aaa_failure_logs) > 5 else "")
                    )
                if sw_exception_logs:
                    failures.append(
                        f"**Software exception logs found ({len(sw_exception_logs)}):**\n"
                        + "\n".join(f"  • {l}" for l in sw_exception_logs[:5])
                        + ("\n  ... (additional omitted)" if len(sw_exception_logs) > 5 else "")
                    )
                if persistent_error_logs:
                    persistent_details = [
                        f"  • '{sig}' occurred {error_sig_counter[sig]} times"
                        for sig in persistent_error_logs
                    ]
                    failures.append(
                        f"**Persistent (recurring) severity 3 errors found ({len(persistent_error_logs)}):**\n"
                        + "\n".join(persistent_details)
                    )

                # Build summary
                result_summary = (
                    f"• Total log entries checked: {total_logs}\n"
                    f"• Critical severity (0/1/2): {len(critical_logs)}\n"
                    f"• Hardware error logs: {len(hardware_error_logs)}\n"
                    f"• Config rollback logs: {len(config_rollback_logs)}\n"
                    f"• AAA failure logs: {len(aaa_failure_logs)}\n"
                    f"• SW exception logs: {len(sw_exception_logs)}\n"
                    f"• Persistent severity 3 errors: {len(persistent_error_logs)}"
                )

                context['display_context'] = "System Log -> State"

                if (
                    not critical_logs
                    and not hardware_error_logs
                    and not config_rollback_logs
                    and not aaa_failure_logs
                    and not sw_exception_logs
                    and not persistent_error_logs
                ):
                    # PASSED
                    return self.format_verification_result(
                        status=ResultStatus.PASSED,
                        context=context,
                        reason=(
                            f"**System Log Check PASSED**\n\n"
                            f"All {total_logs} system log entries are free of critical errors.\n\n"
                            f"**Pass Conditions:**\n"
                            f"• No log entries with severity 0, 1, or 2 (Emergency/Alert/Critical)\n"
                            f"• No log entries indicating hardware failures, configuration rollbacks, AAA failures, or software exceptions\n"
                            f"• No persistent or recurring severity 3 (Error) messages\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**System Log Status:**\n"
                            f"• Total logs checked: {total_logs}\n"
                            f"• All critical error checks passed: Yes\n"
                            f"• Command execution duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )
                else:
                    # FAILED
                    return self.format_verification_result(
                        status=ResultStatus.FAILED,
                        context=context,
                        reason=(
                            f"**System Log Check FAILED**\n\n"
                            f"One or more system log entries indicate critical errors or issues.\n\n"
                            f"**Validation Results:**\n"
                            f"{result_summary}\n\n"
                            f"**Detailed Failures:**\n"
                            f"{chr(10).join(failures)}\n\n"
                            f"**System Log Status:**\n"
                            f"• Total logs checked: {total_logs}\n"
                            f"• Critical severity logs: {len(critical_logs)}\n"
                            f"• Hardware error logs: {len(hardware_error_logs)}\n"
                            f"• Config rollback logs: {len(config_rollback_logs)}\n"
                            f"• AAA failure logs: {len(aaa_failure_logs)}\n"
                            f"• SW exception logs: {len(sw_exception_logs)}\n"
                            f"• Persistent severity 3 errors: {len(persistent_error_logs)}\n\n"
                            f"**Please verify:**\n"
                            f"• Hardware status and replace failed components\n"
                            f"• Configuration history for rollbacks or aborts\n"
                            f"• AAA server/device user authentication configuration\n"
                            f"• Software version and known bugs (if exceptions found)\n"
                            f"• Recurring error messages for root cause analysis\n"
                            f"• Device clock and log buffer size (for completeness)\n"
                            f"• See sample log entries above for details\n"
                            f"• Command execution duration: {api_duration:.2f}s"
                        ),
                        api_duration=api_duration,
                    )

            except Exception as e:
                error_msg = f"Exception during system log health check: {str(e)}"
                self.logger.error(
                    f"Exception for System Log Health Check: {error_msg}",
                    exc_info=True,
                )
                context["display_context"] = "System Log -> State"
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