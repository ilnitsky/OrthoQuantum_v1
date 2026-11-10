#!/usr/bin/env bash
# Rebuild only this branch's main application; never pull or switch branches.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$script_dir/compose.sh" up -d --build
