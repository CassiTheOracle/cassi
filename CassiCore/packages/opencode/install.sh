#!/usr/bin/env bash
# Install / update the CassiCore opencode plugin.
#
# Symlinks integrations/opencode/src/cassicore.mjs into
# ~/.config/opencode/plugins/cassicore.mjs, and removes the older
# cassicore-footprint.mjs if present (the new plugin supersedes it).
#
# After install:
#   1. Make sure CassiCore daemon is running:  ./bin/cassicore boot start
#   2. Restart opencode to pick up the new plugin
#   3. Verify with:  curl --unix-socket ~/.cassicore/admin.sock http://localhost/health
#
# Re-run this script after pulling updates to the plugin source.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="${SCRIPT_DIR}/src/cassicore.mjs"
TARGET_DIR="${HOME}/.config/opencode/plugins"
TARGET="${TARGET_DIR}/cassicore.mjs"
LEGACY="${TARGET_DIR}/cassicore-footprint.mjs"

if [[ ! -f "${SOURCE}" ]]; then
  echo "error: plugin source not found at ${SOURCE}" >&2
  exit 1
fi

mkdir -p "${TARGET_DIR}"

# Remove old footprint plugin (now superseded) and any prior install
if [[ -e "${LEGACY}" || -L "${LEGACY}" ]]; then
  echo "Removing legacy ${LEGACY}"
  rm -f "${LEGACY}"
fi
if [[ -e "${TARGET}" || -L "${TARGET}" ]]; then
  rm -f "${TARGET}"
fi

ln -s "${SOURCE}" "${TARGET}"
echo "Installed CassiCore opencode plugin:"
echo "  ${TARGET} -> ${SOURCE}"
echo
echo "Restart opencode to load the plugin. Verify CassiCore daemon is up:"
echo "  curl --unix-socket ~/.cassicore/admin.sock http://localhost/health"
