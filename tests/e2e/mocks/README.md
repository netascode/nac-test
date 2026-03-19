# Mock Server for E2E Testing

This directory contains a mock API server and related utilities for E2E testing of nac-test.

## Components

- **mock_server.py** - Flask-based mock API server class (used by pytest fixtures)
- **mock_server_ctl.py** - Standalone control script for manual testing/profiling
- **mock_api_config.yaml** - Endpoint configuration (paths, responses, status codes)
- **mock_unicon.py** - Mock Unicon device for PyATS D2D tests

## Standalone Server Usage

For manual testing, debugging, or performance profiling, use the control script:

```bash
# Start server (daemonizes by default)
python mock_server_ctl.py start

# Start on custom port
python mock_server_ctl.py start --port 8080

# Start in foreground (for debugging)
python mock_server_ctl.py start --foreground

# Check server status
python mock_server_ctl.py status

# Stop server
python mock_server_ctl.py stop
```

### Server State

The server writes its state to `/tmp/nac-test-mock-server.json`:
```json
{
  "pid": 12345,
  "port": 5555,
  "started_at": "2026-02-23T10:30:00+00:00"
}
```

Logs are written to `/tmp/nac-test-mock-server.log`.

## Programmatic Usage (Pytest)

For E2E tests, use the `MockAPIServer` class directly:

```python
from tests.e2e.mocks.mock_server import MockAPIServer

server = MockAPIServer(host="127.0.0.1", port=0)  # port=0 for OS-assigned
server.load_from_yaml("mock_api_config.yaml")
server.start()

# ... run tests against server.url ...

server.stop()
```

## Adding Endpoints

Edit `mock_api_config.yaml` to add new endpoints:

```yaml
endpoints:
  - name: "My new endpoint"
    path_pattern: "/api/v1/resource"
    match_type: "exact"  # exact, contains, starts_with, regex
    method: "GET"        # optional, defaults to any method
    status_code: 200
    response_data:
      key: "value"
```

### Match Types

- **exact** - Path must match exactly
- **contains** - Path must contain the pattern
- **starts_with** - Path must start with the pattern  
- **regex** - Pattern is a regular expression
