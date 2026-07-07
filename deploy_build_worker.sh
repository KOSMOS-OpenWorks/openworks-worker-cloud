#!/bin/bash
set -euo pipefail

# Deploy build-worker to db.xwork.cloud
#
# Usage: ./deploy_build_worker.sh [TAG]

IMAGE="codeberg.org/kosmos-eu/openworks-build-worker"
TAG="${1:-20260702-1712}"
HOST="db.xwork.cloud"
CONTAINER="openworks-build-worker"

# OpenCloud connection
OC_URL="https://cloud.brandis.eu"
OC_USER="witt"
OC_TOKEN="staunch dictate mating upfront earphone pushchair"

echo "=== Deploy build-worker to ${HOST} ==="

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
    # - connected to cloud.brandis.eu
    podman run -d --name ${CONTAINER} \
        --privileged \
        --restart unless-stopped \
        -v /data/builderspace:/build:rw \
        -e OPENWORKS_URL=${OC_URL} \
        -e OPENWORKS_USER=${OC_USER} \
        -e 'OPENWORKS_TOKEN=${OC_TOKEN}' \
        -e OPENWORKS_PICK=build-kosmos \
        -e OPENWORKS_CAPACITY=1 \
        ${IMAGE}:${TAG}

    sleep 3
    echo ''
    echo 'Build-worker deployed.'
    podman logs --tail 5 ${CONTAINER} 2>&1
"

echo "=== Done ==="
echo ""
echo "Next: Add worker 'witt' to pipe-matrix for build-kosmos:"
echo "  curl -X PUT https://cloud.brandis.eu/api/v0/jobs/matrix/workers/witt"
echo "    -d '{\"slots\":{\"build-kosmos\":1}}'"
