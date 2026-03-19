#!/usr/bin/env bash
set -euo pipefail

# Start mock server
python /Users/oboehmer/Documents/DD/nac-test/tests/e2e/mocks/start_server.py

echo "======================================"
echo "Running CONSOLIDATED test (2 verification types in 1 subprocess)"
echo "======================================"
echo ""

cd /Users/oboehmer/Documents/DD/nac-test/workspace/scale

/Users/oboehmer/Documents/DD/nac-test/.venv/bin/nac-test \
  --data data/ \
  --templates templates/tests/d2d/ \
  --output results_consolidated/ \
  --pyats

# Stop mock server
python /Users/oboehmer/Documents/DD/nac-test/tests/e2e/mocks/stop_server.py

echo ""
echo "✅ Consolidated test complete!"
