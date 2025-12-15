# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import os
import filecmp
from pathlib import Path

import yaml  # type: ignore
from typer.testing import CliRunner
import pytest

import nac_test.cli.main

pytestmark = pytest.mark.integration


def validate_pyats_results(output_dir: str | Path) -> None:
    """Validate PyATS test results from results.json files.

    Args:
        output_dir: Base output directory containing pyats_results/

    Raises:
        AssertionError: If validation fails (no tests run, tests failed, etc.)
    """
    output_path = Path(output_dir)
    pyats_results_dir = output_path / "pyats_results"
    assert pyats_results_dir.exists(), (
        f"PyATS results directory not found: {pyats_results_dir}"
    )

    # Find all results.json files (can be in api/ or d2d/ subdirs)
    results_files = list(pyats_results_dir.glob("*/results.json"))
    assert len(results_files) > 0, f"No results.json files found in {pyats_results_dir}"

    # Validate each results.json file
    for results_file in results_files:
        with open(results_file) as f:
            results_data = yaml.safe_load(f)

        # Check that results were generated
        assert "report" in results_data, f"No 'report' key in {results_file}"
        assert "summary" in results_data["report"], (
            f"No 'summary' in report for {results_file}"
        )

        summary = results_data["report"]["summary"]

        # Verify tests were run
        assert summary["total"] > 0, (
            f"No tests were run in {results_file.parent.name}: total={summary['total']}"
        )

        # Verify 100% success rate
        assert summary["success_rate"] == 100.0, (
            f"Tests failed in {results_file.parent.name}: "
            f"success_rate={summary['success_rate']}%, "
            f"passed={summary['passed']}, failed={summary['failed']}, "
            f"errored={summary['errored']}"
        )


def test_nac_test(tmpdir: str) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            tmpdir,
        ],
    )
    assert result.exit_code == 0


def test_nac_test_env(tmpdir: str) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_env/"
    templates_path = "tests/integration/fixtures/templates/"
    os.environ["DEF"] = "value"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            tmpdir,
        ],
    )
    assert result.exit_code == 0


def test_nac_test_filter(tmpdir: str) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_filter/"
    filters_path = "tests/integration/fixtures/filters/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-f",
            filters_path,
            "-o",
            tmpdir,
        ],
    )
    assert result.exit_code == 0


def test_nac_test_test(tmpdir: str) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_test/"
    tests_path = "tests/integration/fixtures/tests/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "--tests",
            tests_path,
            "-o",
            tmpdir,
        ],
    )
    assert result.exit_code == 0


def test_nac_test_render(tmpdir: str) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_fail/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            tmpdir,
            "--render-only",
        ],
    )
    assert result.exit_code == 0
    templates_path = "tests/integration/fixtures/templates_missing/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            tmpdir,
            "--render-only",
        ],
    )
    assert result.exit_code == 1
    templates_path = "tests/integration/fixtures/templates_missing_default/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            tmpdir,
            "--render-only",
        ],
    )
    assert result.exit_code == 0


def test_nac_test_list(tmpdir: str) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_list/"
    templates_path = "tests/integration/fixtures/templates_list/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            tmpdir,
        ],
    )
    assert os.path.exists(os.path.join(tmpdir, "ABC", "test1.robot"))
    assert os.path.exists(os.path.join(tmpdir, "DEF", "test1.robot"))
    assert os.path.exists(os.path.join(tmpdir, "_abC", "test1.robot"))
    assert result.exit_code == 0


def test_nac_test_list_folder(tmpdir: str) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_list/"
    templates_path = "tests/integration/fixtures/templates_list_folder/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            tmpdir,
        ],
    )
    assert os.path.exists(os.path.join(tmpdir, "test1", "ABC.robot"))
    assert os.path.exists(os.path.join(tmpdir, "test1", "DEF.robot"))
    assert os.path.exists(os.path.join(tmpdir, "test1", "_abC.robot"))
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "cli_args, expected_filename",
    [
        ([], "merged_data_model_test_variables.yaml"),
        (["--merged-data-filename", "custom.yaml"], "custom.yaml"),
    ],
)
def test_nac_test_render_output_model(
    tmpdir: str, cli_args: list[str], expected_filename: str
) -> None:
    """Tests the creation of the merged data model YAML file."""
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_merge/"
    templates_path = "tests/integration/fixtures/templates/"
    output_model_path = os.path.join(tmpdir, expected_filename)
    expected_model_path = "tests/integration/fixtures/data_merge/result.yaml"

    base_args = [
        "-d",
        os.path.join(data_path, "file1.yaml"),
        "-d",
        os.path.join(data_path, "file2.yaml"),
        "-t",
        templates_path,
        "-o",
        tmpdir,
        "--render-only",
    ]

    result = runner.invoke(nac_test.cli.main.app, base_args + cli_args)
    assert result.exit_code == 0
    assert os.path.exists(output_model_path)
    assert filecmp.cmp(output_model_path, expected_model_path, shallow=False)


@pytest.mark.skip("not yet finished")
def test_nac_test_pyats(tmpdir: str) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_pyats/"
    result = runner.invoke(
        nac_test.cli.main.app,
        ["-d", data_path, "-t", templates_path, "-o", tmpdir, "--verbosity", "DEBUG"],
    )
    assert result.exit_code == 0
    assert False, "not yet finished"


def test_nac_test_qs(mock_api_server) -> None:
    runner = CliRunner()
    os.environ["ACI_URL"] = mock_api_server.url
    os.environ["ACI_USERNAME"] = "does not matter"
    os.environ["ACI_PASSWORD"] = "does not matter"
    os.environ["CONTROLLER_TYPE"] = "ACI"

    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_quicksilver/"
    output_dir = "/tmp/nac-test-qs"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            output_dir,
            "--verbosity",
            "DEBUG",
        ],
    )

    # test failures are currently not reflected in exit code, see #425
    # assert result.exit_code == 0

    # Verify PyATS test results using helper function
    validate_pyats_results(output_dir)


def test_nac_test_with_mock_api_yaml(mock_api_server) -> None:
    """Example test demonstrating mock API server with YAML config.

    The server auto-starts with configuration from fixtures/mock_api_config.yaml.
    """
    import requests

    # Server is already running with YAML configuration loaded
    # Test endpoints defined in mock_api_config.yaml

    # Test /api/devices endpoint
    response = requests.get(f"{mock_api_server.url}/api/devices")
    assert response.status_code == 200
    data = response.json()
    assert "devices" in data
    assert len(data["devices"]) == 2
    assert data["devices"][0]["name"] == "Router1"

    # Test /api/config endpoint
    response = requests.get(f"{mock_api_server.url}/api/config")
    assert response.status_code == 200
    assert response.json()["config"]["timeout"] == 30

    # Test error endpoint
    response = requests.get(f"{mock_api_server.url}/api/error")
    assert response.status_code == 500
    assert "error" in response.json()


def test_nac_test_with_mock_api_complex_urls(mock_api_server) -> None:
    """Test complex URLs with query parameters (like ACI API).

    This demonstrates handling URLs with special characters and query strings.
    """
    import requests

    # Test ACI-style URL with complex query parameters
    url = f'{mock_api_server.url}/node/class/infraWiNode.json?query-target-filter=wcard(infraWiNode.dn,"topology/pod-1/node-1/")'
    response = requests.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["totalCount"] == "3"
    assert "imdata" in data

    # Test generic infraWiNode query (should match the second pattern)
    url = f"{mock_api_server.url}/node/class/infraWiNode.json?query-target=self"
    response = requests.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["totalCount"] == "3"


# def test_nac_test_with_mock_api_dynamic(mock_api_server) -> None:
#     """Example test showing dynamic endpoint configuration.

#     You can add endpoints at runtime even with YAML config loaded.
#     """
#     import requests

#     # Add a new endpoint dynamically
#     mock_api_server.add_endpoint(
#         name='Custom endpoint',
#         path_pattern='/api/custom',
#         status_code=201,
#         response_data={'message': 'Created', 'id': 123},
#         match_type='exact'
#     )

#     # Test the dynamically added endpoint
#     response = requests.get(f"{mock_api_server.url}/api/custom")
#     assert response.status_code == 201
#     assert response.json()['id'] == 123

#     # Add endpoint with pattern matching for dynamic IDs
#     mock_api_server.add_endpoint(
#         name='User by ID',
#         path_pattern='^/api/users/[0-9]+$',
#         status_code=200,
#         response_data={'user': 'John Doe'},
#         match_type='regex'
#     )

#     # Test pattern matching
#     response = requests.get(f"{mock_api_server.url}/api/users/123")
#     assert response.status_code == 200
#     assert response.json()['user'] == 'John Doe'
