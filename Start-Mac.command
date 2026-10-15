#!/bin/bash
set -euo pipefail
exec bash "$(dirname "$0")/setup/start-mac.sh" "$@"
