#!/bin/bash
# Test runner for codebase-memory-gate
# Run: cd <this-dir> && ./run-tests.sh
#
# Environment variables (machine-specific):
#   CBM_PROXY_PATH  Absolute path to codebase-memory-mcp-omp-proxy on this
#                   machine. The proxy is a runtime-installed sibling of the
#                   extension (see docs/maintenance/runtime-config-inventory.md);
#                   it is intentionally NOT migrated into this target because
#                   it is a per-machine install, not reusable configuration.
#                   If unset, the proxy tests are skipped.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "Codebase Memory Gate & Proxy Tests"
echo "============================================================"

# Unit tests (fast, no OMP spawn)
echo ""
echo "--- Unit Tests (Classification Logic) ---"
if command -v bun &>/dev/null; then
    echo "Running classification unit tests..."
    bun run gate-classification.test.mjs
    bun run behavior-smoke.test.mjs
else
    echo "bun not available, skipping classification tests"
fi

# E2E tests (spawn real OMP processes). The e2e harness depends on
# environment variables documented at the top of e2e-smoke.test.mjs.
echo ""
echo "--- E2E Smoke Tests (Real OMP Processes) ---"
echo "Running E2E smoke tests..."
node e2e-smoke.test.mjs

# Proxy tests (proxy process). The proxy itself lives outside this
# target on the local machine; we only know its path through the
# CBM_PROXY_PATH environment variable.
echo ""
echo "--- Proxy Tests ---"
PROXY_PATH="${CBM_PROXY_PATH:-}"
if [ -n "$PROXY_PATH" ] && [ -f "$PROXY_PATH" ]; then
    echo "Running proxy EPIPE/ID remapping tests..."
    node proxy-epipe.test.mjs
else
    echo "Proxy path not set (CBM_PROXY_PATH) or not found; skipping proxy tests"
fi

echo ""
echo "============================================================"
echo "All tests completed"
echo "============================================================"
