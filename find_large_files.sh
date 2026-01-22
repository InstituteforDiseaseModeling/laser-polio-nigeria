#!/bin/bash
set -euo pipefail

TARGET_DIR="${1:-.}"
MAX_RESULTS="${2:-50}"

echo "🔍 Scanning '$TARGET_DIR' for largest files..."
echo "📦 Showing top $MAX_RESULTS results"

# Find all files, list with size in human-readable form, sort by size descending
find "$TARGET_DIR" -type f -exec du -h {} + 2>/dev/null |
  sort -hr |
  head -n "$MAX_RESULTS"
