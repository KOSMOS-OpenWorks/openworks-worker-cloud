#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="codeberg.org/kosmos-openworks/openworks-worker-cloud"
TAG="$(date +%Y%m%d-%H%M)"

echo "=== Build openworks-worker: ${IMAGE}:${TAG} ==="

if command -v buildah &>/dev/null; then
    TMPDIR="${TMPDIR:-/tmp}" buildah bud --no-cache --network=host --security-opt label=disable -t "${IMAGE}:${TAG}" "$SCRIPT_DIR"
else
    TMPDIR="${TMPDIR:-/tmp}" podman build --no-cache --network=host --security-opt label=disable -t "${IMAGE}:${TAG}" "$SCRIPT_DIR"
fi

echo ""
echo "=== Built: ${IMAGE}:${TAG} ==="
echo ""
echo "Usage:"
echo "  podman run --rm ${IMAGE}:${TAG} --help"
echo ""
echo "  podman run -d --name openworks-worker \\"
echo "    ${IMAGE}:${TAG} \\"
echo "    --url https://cloud.example.com \\"
echo "    --token <worker-api-token> \\"
echo "    --pick md-to-pdf,zip-create \\"
echo "    --capacity 2"
echo ""
echo "Push:"
echo "  podman push ${IMAGE}:${TAG}"
echo "  podman tag ${IMAGE}:${TAG} ${IMAGE}:latest && podman push ${IMAGE}:latest"
