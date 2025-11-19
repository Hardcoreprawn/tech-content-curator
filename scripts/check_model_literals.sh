#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PATTERN='"gpt-[0-9a-zA-Z.-]+"|"dall-e-3"|"dalle-3"|"o1-[0-9a-zA-Z.-]+"'

ALLOWLIST_FILE="scripts/model_literal_allowlist.txt"
mapfile -t ALLOWLIST < <(grep -v '^#' "$ALLOWLIST_FILE" | sed '/^$/d')

EXCLUDES=(
  "--exclude=src/models.py"
  "--exclude=src/config.py"
  "--exclude=src/utils/pricing.py"
)

MATCHES=$(grep -R --line-number -E "$PATTERN" src/ \
    --exclude-dir tests \
    --exclude-dir docs \
    --exclude-dir __pycache__ \
    "${EXCLUDES[@]}" || true)

if [[ -z "$MATCHES" ]]; then
  echo "No disallowed model literals detected."
  exit 0
fi

VIOLATIONS=()
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  file="${line%%:*}"
  allow=false
  for entry in "${ALLOWLIST[@]}"; do
    if [[ "$file" == "$entry"* ]]; then
      allow=true
      break
    fi
  done
  if [[ "$allow" == false ]]; then
    VIOLATIONS+=("$line")
  fi
done <<< "$MATCHES"

if ((${#VIOLATIONS[@]} > 0)); then
  printf '%s
' "${VIOLATIONS[@]}" >&2
  echo "Found hardcoded model strings - replace them with config.stage_models entries or pricing data." >&2
  exit 1
fi

echo "Only allowlisted literals detected."
