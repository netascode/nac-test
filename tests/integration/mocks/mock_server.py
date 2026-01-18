# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

"""Flask mock server for API testing."""

import json
import logging
import re
import threading
from pathlib import Path
from typing import Any

import yaml
from flask import Flask, jsonify, request

# Set up logger for mock server
logger = logging.getLogger(__name__)


# Add a custom handler that silently catches I/O errors during teardown
class SafeHandler(logging.Handler):
    """Handler that wraps another handler and catches I/O errors."""

    def __init__(self, wrapped_handler: logging.Handler):
        super().__init__()
        self.wrapped_handler = wrapped_handler
        self.setLevel(wrapped_handler.level)
        self.setFormatter(wrapped_handler.formatter)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.wrapped_handler.emit(record)
        except (ValueError, OSError):
            # Silently ignore I/O errors during pytest teardown
            pass


# Wrap existing handlers with safe handlers
_original_handlers = logger.handlers.copy()
logger.handlers.clear()
for handler in _original_handlers:
    logger.addHandler(SafeHandler(handler))


class MockAPIServer:
    """A configurable mock API server for testing."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5555) -> None:
        """Initialize the mock server.

        Args:
            host: Host to bind the server to
            port: Port to bind the server to
        """
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.server_thread: threading.Thread | None = None
        self.endpoint_configs: list[dict[str, Any]] = []

        # Configure Flask to suppress startup messages
        werkzeug_log = logging.getLogger("werkzeug")
        werkzeug_log.setLevel(logging.ERROR)

        logger.info(f"Initializing MockAPIServer on {host}:{port}")

        # Setup catch-all route
        self.app.add_url_rule(
            "/<path:path>",
            "catch_all",
            self._handle_request,
            methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        )
        self.app.add_url_rule(
            "/",
            "root",
            self._handle_request,
            methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        )

    def add_endpoint(
        self,
        name: str,
        path_pattern: str,
        status_code: int = 200,
        response_data: Any = None,
        method: str | None = None,
        match_type: str = "exact",
    ) -> None:
        """Add a mock endpoint configuration.

        Args:
            name: Descriptive name for the endpoint (for logging/debugging)
            path_pattern: Pattern to match against the full request URL (path + query string)
            status_code: HTTP status code to return
            response_data: Data to return as JSON
            method: HTTP method to match (GET, POST, etc.). None matches all methods
            match_type: How to match the pattern:
                - "exact": Exact string match
                - "contains": Path contains the pattern
                - "regex": Pattern is a regular expression
                - "starts_with": Path starts with the pattern
        """
        endpoint_config = {
            "name": name,
            "path_pattern": path_pattern,
            "status_code": status_code,
            "response_data": response_data or {},
            "method": method.upper() if method else None,
            "match_type": match_type,
        }
        self.endpoint_configs.append(endpoint_config)

        method_str = endpoint_config["method"] or "ANY"
        logger.debug(
            f"Added endpoint [{len(self.endpoint_configs)}]: "
            f"{method_str} '{path_pattern}' ({match_type}) -> {status_code} | {name}"
        )

    def add_endpoints(self, endpoints: list[dict[str, Any]]) -> None:
        """Add multiple endpoint configurations at once.

        Args:
            endpoints: List of endpoint configurations. Each dict should have keys:
                - name: Descriptive name
                - path_pattern: URL pattern to match
                - status_code: HTTP status code (default: 200)
                - response_data: Response data (default: {})
                - method: HTTP method (optional, default: None = all methods)
                - match_type: Matching strategy (default: "exact")
        """
        for endpoint in endpoints:
            self.add_endpoint(
                name=endpoint["name"],
                path_pattern=endpoint["path_pattern"],
                status_code=endpoint.get("status_code", 200),
                response_data=endpoint.get("response_data", {}),
                method=endpoint.get("method"),
                match_type=endpoint.get("match_type", "exact"),
            )

    def load_from_yaml(self, yaml_path: str | Path) -> None:
        """Load endpoint configuration from a YAML file.

        Args:
            yaml_path: Path to YAML configuration file

        The YAML file should have the following structure:
            endpoints:
              - name: "Get devices"
                path_pattern: "/api/devices"
                match_type: "exact"
                status_code: 200
                response_data:
                  devices: []
              - name: "ACI node query"
                path_pattern: "node/class/infraWiNode.json"
                match_type: "contains"
                method: "GET"
                status_code: 200
                response_data:
                  totalCount: "1"
        """
        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"YAML configuration file not found: {yaml_path}")

        with open(yaml_path) as f:
            config = yaml.safe_load(f)

        if not config or "endpoints" not in config:
            raise ValueError(f"YAML file must contain 'endpoints' key: {yaml_path}")

        if not isinstance(config["endpoints"], list):
            raise ValueError(f"'endpoints' must be a list in YAML file: {yaml_path}")

        endpoint_count_before = len(self.endpoint_configs)
        self.add_endpoints(config["endpoints"])
        endpoint_count_after = len(self.endpoint_configs)

        logger.info(
            f"Loaded {endpoint_count_after - endpoint_count_before} endpoints from {yaml_path.name}"
        )

    def _match_path(self, request_path: str, pattern: str, match_type: str) -> bool:
        """Check if request path matches the pattern based on match type.

        Args:
            request_path: The full request path including query string
            pattern: The pattern to match against
            match_type: Type of matching (exact, contains, regex, starts_with)

        Returns:
            True if the path matches, False otherwise
        """
        if match_type == "exact":
            return request_path == pattern
        elif match_type == "contains":
            return pattern in request_path
        elif match_type == "starts_with":
            return request_path.startswith(pattern)
        elif match_type == "regex":
            return bool(re.match(pattern, request_path))
        return False

    def _handle_request(self, path: str = "") -> tuple[Any, int]:
        """Handle incoming requests and return configured responses."""
        # Get full request URL including query parameters
        full_path = f"/{path}" if path else "/"
        if request.query_string:
            full_path = f"{full_path}?{request.query_string.decode('utf-8')}"

        request_method = request.method

        logger.info(f">>> Incoming request: {request_method} {full_path}")

        # Log request details at DEBUG level
        logger.debug(f"    Headers: {dict(request.headers)}")
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                request_body = request.get_data(as_text=True)
                if request_body:
                    logger.debug(
                        f"    Body: {request_body[:500]}{'...' if len(request_body) > 500 else ''}"
                    )
            except Exception:
                logger.debug("    Body: <unable to read>")

        logger.debug(
            f"    Checking {len(self.endpoint_configs)} endpoint(s) for match..."
        )

        # Iterate through endpoint configs and find first match
        for idx, config in enumerate(self.endpoint_configs, 1):
            config_method = config["method"] or "ANY"

            # Check method match
            if config["method"] and config["method"] != request_method:
                logger.debug(
                    f"    [{idx}] SKIP (method mismatch): {config_method} != {request_method} | {config['name']}"
                )
                continue

            # Check path match
            match_result = self._match_path(
                full_path, config["path_pattern"], config["match_type"]
            )
            if match_result:
                response_size = len(str(config["response_data"]))
                logger.info(
                    f"    [{idx}] ✓ MATCH: {config_method} '{config['path_pattern']}' "
                    f"({config['match_type']}) | {config['name']}"
                )
                logger.info(
                    f"<<< Response: {config['status_code']} (~{response_size} bytes)"
                )

                # Log response data at DEBUG level
                response_json = json.dumps(config["response_data"], indent=2)
                if len(response_json) > 1000:
                    logger.debug(
                        f"    Response data (truncated):\n{response_json[:1000]}..."
                    )
                else:
                    logger.debug(f"    Response data:\n{response_json}")

                return jsonify(config["response_data"]), config["status_code"]
            else:
                logger.debug(
                    f"    [{idx}] no match: '{config['path_pattern']}' ({config['match_type']}) | {config['name']}"
                )

        # Default response for unconfigured endpoints
        error_response = {"error": "Endpoint not configured", "path": full_path}
        logger.warning(
            f"<<< No matching endpoint found for: {request_method} {full_path}"
        )
        logger.warning("    Returning 404 Not Found")
        logger.debug(f"    Response data:\n{json.dumps(error_response, indent=2)}")
        return jsonify(error_response), 404

    def start(self) -> None:
        """Start the mock server in a background thread."""
        if self.server_thread and self.server_thread.is_alive():
            logger.warning(f"Server already running on {self.url}")
            return

        logger.info(f"Starting mock server on {self.url}")
        logger.info(f"Configured with {len(self.endpoint_configs)} endpoint(s)")

        def run_server() -> None:
            self.app.run(
                host=self.host, port=self.port, threaded=True, use_reloader=False
            )

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        # Give server time to start
        import time

        time.sleep(0.5)

        logger.info(f"✓ Mock server ready at {self.url}")

    def stop(self) -> None:
        """Stop the mock server."""
        # Flask's development server doesn't have a clean shutdown method
        # Using daemon threads ensures cleanup on test exit
        # Note: Don't log here as pytest may have closed logging streams during teardown
        pass

    @property
    def url(self) -> str:
        """Get the base URL of the server."""
        return f"http://{self.host}:{self.port}"
