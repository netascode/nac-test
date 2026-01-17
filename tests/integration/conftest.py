# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Pytest fixtures for integration tests."""

import os
from collections.abc import Generator
from pathlib import Path

import pytest

from tests.integration.mocks.mock_server import MockAPIServer

# Path to the default YAML configuration file
DEFAULT_CONFIG_PATH = Path(__file__).parent / "fixtures" / "mock_api_config.yaml"

# To see mock server logs, set logging level to INFO or DEBUG in your tests:
#
# INFO level shows:
#   - Server startup/shutdown
#   - Incoming requests and matched endpoints
#   - Response status codes
#
# DEBUG level additionally shows:
#   - Request headers and body
#   - Full response data (JSON)
#   - All pattern matching attempts
#
# Enable with:
#   logging.basicConfig(level=logging.INFO)
# or for more detail:
#   logging.basicConfig(level=logging.DEBUG)
# or target just the mock server:
#   logging.getLogger('tests.integration.mock_server').setLevel(logging.DEBUG)


@pytest.fixture(scope="session")
def mock_api_server() -> Generator[MockAPIServer, None, None]:
    """Provide a mock API server that auto-starts for all integration tests.

    The server starts automatically once per test session and loads configuration
    from the YAML file at tests/integration/fixtures/mock_api_config.yaml.

    You can override the config file by setting the MOCK_API_CONFIG environment variable.

    The server is accessible at http://127.0.0.1:5555 by default.

    Example usage in tests:
        def test_api_call(mock_api_server):
            import requests
            # Server is already running with YAML config loaded
            response = requests.get(f"{mock_api_server.url}/api/devices")
            assert response.status_code == 200

            # You can also add endpoints dynamically
            mock_api_server.add_endpoint(
                name='Custom',
                path_pattern='/api/custom',
                status_code=200,
                response_data={'custom': 'data'},
                match_type='exact'
            )
    """
    server = MockAPIServer()

    # Load configuration from YAML file
    config_path = os.environ.get("MOCK_API_CONFIG", str(DEFAULT_CONFIG_PATH))
    config_file = Path(config_path)

    if config_file.exists():
        server.load_from_yaml(config_file)
    else:
        # If no config file exists, just start the server without pre-configured endpoints
        pass

    server.start()
    yield server
    server.stop()
