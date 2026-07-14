#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${PUSH_REGISTRY:-codeberg.org}/${PUSH_ORG:-kosmos-openworks}/openworks-worker-cloud"
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
echo ""
echo "    ${IMAGE}:${TAG} \\"
echo ""

if [ -n "${PUSH_TOKEN:-}" ]; then
    CREDS="${PUSH_USER:-token}:${PUSH_TOKEN}"
    buildah push --creds="$CREDS" "${IMAGE}:${TAG}"
    buildah tag "${IMAGE}:${TAG}" "${IMAGE}:latest"
    buildah push --creds="$CREDS" "${IMAGE}:latest"
fi

echo "=== Built: ${IMAGE}:${TAG} ==="
