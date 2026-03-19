"""
Minimal reproduction case for pyATS step.failed()/passed() data parameter bug.

The `data` parameter passed to step result methods is not persisted to results.json.

Run with:
    uv run pyats run job job.py --testbed-file empty_testbed.yaml

Or standalone:
    uv run pyats run testscript test_step_data_bug.py --testbed-file empty_testbed.yaml

Then check results.json - the 'data' field will be missing from step results.
"""

from pyats import aetest


class TestStepDataBug(aetest.Testcase):
    """Demonstrate that step.failed(data=...) does not persist data to results.json."""

    @aetest.test
    def test_step_data_not_persisted(self, steps):
        """This test shows that data passed to step.failed() is lost."""

        # Step 1: Pass data to step.failed()
        with steps.start("Step with data that should appear in results.json") as step:
            test_data = {
                "verification_summary": {
                    "total_checked": 10,
                    "passed": 8,
                    "failed": 2,
                },
                "custom_field": "this should be in results.json",
            }

            # This data should appear in results.json under result.data
            # But it doesn't due to the bug
            step.failed(
                reason="Intentional failure to demonstrate bug",
                data=test_data,
            )

    @aetest.test
    def test_step_passed_data_not_persisted(self, steps):
        """This test shows that data passed to step.passed() is also lost."""

        with steps.start("Passing step with data") as step:
            test_data = {
                "metrics": {"latency_ms": 42, "throughput": 1000},
            }

            # This data should also appear in results.json
            step.passed(
                reason="Success with metrics",
                data=test_data,
            )


if __name__ == "__main__":
    aetest.main()
