#!/usr/bin/env bash
# Deploy/update the staging stack from signed GHCR images (M4, TASK-0005).
# Usage: ./deploy.sh   (reads .env in this directory; override with ENV_FILE=/path/to/env)
set -euo pipefail

cd "$(dirname "$0")"

env_file="${ENV_FILE:-.env}"
if [[ ! -f "${env_file}" ]]; then
  echo "missing env file: ${env_file} (copy .env.example and fill values)" >&2
  exit 1
fi

docker compose --env-file "${env_file}" pull
docker compose --env-file "${env_file}" up -d --remove-orphans
docker compose --env-file "${env_file}" ps
