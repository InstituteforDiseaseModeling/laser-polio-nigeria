#!/bin/bash
set -euo pipefail

TARGET_DIR="${1:-.}"

echo "🔍 Searching for results folders in: $TARGET_DIR"
echo

# Find results-like directories
RESULT_DIRS=$(find "$TARGET_DIR" -type d \( -name "results" -o -name "results_fullscale" \))

if [ -z "$RESULT_DIRS" ]; then
    echo "✅ No 'results' or 'results_fullscale' folders found."
    exit 0
fi

echo "🚨 The following folders will be deleted:"
echo "$RESULT_DIRS"
echo
read -p "❓ Proceed with deletion? [y/N] " CONFIRM

if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo
    echo "🧹 Deleting..."
    echo "$RESULT_DIRS" | xargs rm -rf
    echo "✅ Done. Results folders deleted."
else
    echo "❌ Cancelled. No changes made."
fi
