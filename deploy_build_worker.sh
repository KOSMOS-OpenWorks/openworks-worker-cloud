#!/bin/bash
set -euo pipefail

# Deploy build-worker to db.xwork.cloud
#
# Usage: ./deploy_build_worker.sh [TAG]
#
# Config via env or DIST:
#   OC_URL       OpenCloud URL (default: https://cloud.brandis.eu)
#   OC_USER      Worker user (required)
#   OC_TOKEN     Worker app token (required)
#   OC_CAPACITY  Parallel job capacity (default: 1)
#   OC_PICK      Job types to pick (default: build-pod,build-web)

IMAGE="codeberg.org/kosmos-openworks/openworks-build-worker"
TAG="${1:-latest}"
HOST="db.xwork.cloud"
CONTAINER="openworks-build-worker"

OC_URL="${OC_URL:-https://cloud.brandis.eu}"
OC_USER="${OC_USER:?OC_USER required}"
OC_TOKEN="${OC_TOKEN:?OC_TOKEN required}"
OC_CAPACITY="${OC_CAPACITY:-1}"
OC_PICK="${OC_PICK:-build-pod,build-web}"

echo "=== Deploy build-worker to ${HOST} ==="
echo "  Image:    ${IMAGE}:${TAG}"
echo "  URL:      ${OC_URL}"
echo "  User:     ${OC_USER}"
echo "  Capacity: ${OC_CAPACITY}"
echo "  Pick:     ${OC_PICK}"

ssh "root@${HOST}" "
    # Pull image
    podman pull ${IMAGE}:${TAG}

    # Stop existing
    podman stop ${CONTAINER} 2>/dev/null || true
    podman rm ${CONTAINER} 2>/dev/null || true

    # Create build workspace
    mkdir -p /data/builderspace

    # Run with:
    # - privileged (buildah needs it)
    # - /data/builderspace mounted for temp build files
    podman run -d --name ${CONTAINER} \
        --privileged \
        --restart unless-stopped \
        -v /data/builderspace:/build:rw \
        -e OPENWORKS_URL=${OC_URL} \
        -e OPENWORKS_USER=${OC_USER} \
        -e 'OPENWORKS_TOKEN=${OC_TOKEN}' \
        -e OPENWORKS_PICK=${OC_PICK} \
        -e OPENWORKS_CAPACITY=${OC_CAPACITY} \
        ${IMAGE}:${TAG}

    sleep 3
    echo ''
    echo 'Build-worker deployed.'
    podman logs --tail 5 ${CONTAINER} 2>&1
"

echo "=== Done ==="
