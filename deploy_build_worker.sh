#!/bin/bash
set -euo pipefail

# Deploy build-worker to db.xwork.cloud
#
# Usage: ./deploy_build_worker.sh [TAG]
#
# Config lives on the host at /data/openworks/build-worker.env
# Created once, never overwritten by deploy.
#
# First-time setup on host:
#   mkdir -p /data/openworks
#   cat > /data/openworks/build-worker.env <<'EOF'
#   OPENWORKS_URL=https://cloud.brandis.eu
#   OPENWORKS_USER=witt
#   OPENWORKS_TOKEN=staunch dictate mating upfront earphone pushchair
#   OPENWORKS_PICK=build-pod,build-web
#   OPENWORKS_CAPACITY=1
#   EOF

IMAGE="codeberg.org/kosmos-openworks/openworks-build-worker"
TAG="${1:-latest}"
HOST="db.xwork.cloud"
CONTAINER="openworks-build-worker"
ENV_FILE="/data/openworks/build-worker.env"

echo "=== Deploy build-worker to ${HOST} ==="
echo "  Image:    ${IMAGE}:${TAG}"
echo "  Config:   ${HOST}:${ENV_FILE}"

ssh "root@${HOST}" "
    # Check config exists
    if [ ! -f ${ENV_FILE} ]; then
        echo 'ERROR: ${ENV_FILE} not found on host.'
        echo 'Create it first (see deploy_build_worker.sh header for template).'
        exit 1
    fi

    # Pull image
    podman pull ${IMAGE}:${TAG}

    # Stop existing
    podman stop ${CONTAINER} 2>/dev/null || true
    podman rm ${CONTAINER} 2>/dev/null || true

    # Create build workspace
    mkdir -p /data/builderspace

    # Run with env-file from host + build workspace mount
    podman run -d --name ${CONTAINER} \
        --privileged \
        --restart unless-stopped \
        --env-file ${ENV_FILE} \
        -v /data/builderspace:/build:rw \
        ${IMAGE}:${TAG}

    sleep 3
    echo ''
    echo 'Build-worker deployed.'
    podman logs --tail 5 ${CONTAINER} 2>&1
"

echo "=== Done ==="
