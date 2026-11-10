#!/usr/bin/env bash
# Keep the established 8051 deployment separate from the legacy Dash project.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"
if docker compose version >/dev/null 2>&1; then
  exec docker compose -p orthoquantum_lite -f "$script_dir/docker-compose.yml" "$@"
fi
exec docker-compose -p orthoquantum_lite -f "$script_dir/docker-compose.yml" "$@"
