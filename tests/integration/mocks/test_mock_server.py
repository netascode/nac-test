import requests
from tests.integration.mocks.mock_server import MockAPIServer


def test_mock_api_server(mock_api_server: MockAPIServer) -> None:
    """Example test demonstrating mock API server with YAML config.

    The server auto-starts with configuration from fixtures/mock_api_config.yaml.
    """

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


def test_nac_test_with_mock_api_dynamic(mock_api_server) -> None:
    """Example test showing dynamic endpoint configuration.

    You can add endpoints at runtime even with YAML config loaded.
    """
    import requests

    # Add a new endpoint dynamically
    mock_api_server.add_endpoint(
        name="Custom endpoint",
        path_pattern="/api/custom",
        status_code=201,
        response_data={"message": "Created", "id": 123},
        match_type="exact",
    )

    # Test the dynamically added endpoint
    response = requests.get(f"{mock_api_server.url}/api/custom")
    assert response.status_code == 201
    assert response.json()["id"] == 123

    # Add endpoint with pattern matching for dynamic IDs
    mock_api_server.add_endpoint(
        name="User by ID",
        path_pattern="^/api/users/[0-9]+$",
        status_code=200,
        response_data={"user": "John Doe"},
        match_type="regex",
    )

    # Test pattern matching
    response = requests.get(f"{mock_api_server.url}/api/users/123")
    assert response.status_code == 200
    assert response.json()["user"] == "John Doe"
