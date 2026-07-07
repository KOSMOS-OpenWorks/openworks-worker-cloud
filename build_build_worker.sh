#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="codeberg.org/kosmos-eu/openworks-build-worker"
TAG="$(date +%Y%m%d-%H%M)"

echo "=== Build openworks-build-worker: ${IMAGE}:${TAG} ==="

BUILD_CMD="podman build"
command -v buildah &>/dev/null && BUILD_CMD="buildah bud"
TMPDIR="${TMPDIR:-/tmp}" $BUILD_CMD --network=host --security-opt label=disable \
    -f "$SCRIPT_DIR/Dockerfile.build-worker" \
    -t "${IMAGE}:${TAG}" "$SCRIPT_DIR"

echo ""
echo "=== Built: ${IMAGE}:${TAG} ==="
echo ""
echo "Push:"
echo "  podman push ${IMAGE}:${TAG}"
echo ""
echo "Run on target:"
echo "  podman run -d --name openworks-build-worker \\"
echo "    --privileged \\"
echo "    -e OPENWORKS_URL=https://cloud.brandis.eu \\"
echo "    -e OPENWORKS_USER=witt \\"
echo "    -e 'OPENWORKS_TOKEN=<token>' \\"
echo "    -e OPENWORKS_PICK=build-kosmos \\"
echo "    -e OPENWORKS_CAPACITY=1 \\"
echo "    ${IMAGE}:${TAG}"
