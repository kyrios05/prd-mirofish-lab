#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
engine_root="${MIROFISH_SOURCE_DIR:-$(dirname "$repo_root")/MiroFish-Offline}"

if [[ ! -f "$engine_root/docker-compose.yml" ]]; then
  echo "MiroFish source not found: $engine_root (set MIROFISH_SOURCE_DIR)." >&2
  exit 1
fi

docker compose --project-name mirofish-offline \
  --env-file "$repo_root/apps/api/.env" \
  -f "$engine_root/docker-compose.yml" \
  -f "$repo_root/compose.mirofish.yml" \
  up -d --build mirofish
