#!/bin/bash
# Run the build-worker directly on the host (not in container).
# Needs: Go 1.26+, Node.js/pnpm, Podman, Git, Python 3.11+
#
# Usage: ./run_build_worker.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

export OPENWORKS_URL="${OPENWORKS_URL:-https://cloud.brandis.eu}"
export OPENWORKS_USER="${OPENWORKS_USER:-worker}"
export OPENWORKS_TOKEN="${OPENWORKS_TOKEN:-SET_TOKEN}"
export OPENWORKS_PICK="build-kosmos"
export OPENWORKS_CAPACITY="1"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

echo "=== OpenWorks Build Worker ==="
echo "  URL:  $OPENWORKS_URL"
echo "  User: $OPENWORKS_USER"
echo "  Pick: $OPENWORKS_PICK"
echo ""

cd "$SCRIPT_DIR/worker"
pip install -e . -q 2>/dev/null
exec python -m openworks.cli
