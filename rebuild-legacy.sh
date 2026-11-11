#!/usr/bin/env bash
# Explicit legacy Dash deployment; preserves its existing project and volumes.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"
exec docker-compose -p best_repository_ever -f docker-compose.legacy.yml up -d --build
