#!/usr/bin/env bash
# Build the Stage 2 runner image inside the dedicated Colima VM and print the image id.
# One-time VM setup (no host shares, no agent forwarding), then run this script:
#   colima start codejury-stage2 --arch aarch64 --cpu 2 --memory 2 --mount-type virtiofs --mount ""
# (verify with: ~/.colima/codejury-stage2/colima.yaml has an empty `mounts:` list)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
ctx="${CODEJURY_STAGE2_CONTEXT:-colima-codejury-stage2}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cp "$here/Dockerfile" "$tmp/Dockerfile"
cp "$here/../../../src/codejury/stage2_tools/runner/entry.py" "$tmp/entry.py"
docker --context "$ctx" build --platform linux/arm64 -t codejury-stage2-runner:local "$tmp"
docker --context "$ctx" image inspect --format '{{.Id}}' codejury-stage2-runner:local
echo "export CODEJURY_STAGE2_RUNNER_IMAGE=<id printed above>" >&2
