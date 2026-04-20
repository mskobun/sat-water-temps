#!/usr/bin/env bash
# Upload repo static assets into Miniflare local R2 (bucket multitifs).
# Optional: WRANGLER_PERSIST_TO=... to match wrangler dev --persist-to
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

put_object() {
  local r2_key="$1" local_file="$2" content_type="$3"
  if [[ -n "${WRANGLER_PERSIST_TO:-}" ]]; then
    npx wrangler r2 object put "multitifs/${r2_key}" --local \
      --persist-to "$WRANGLER_PERSIST_TO" \
      --file "$local_file" \
      --content-type "$content_type"
  else
    npx wrangler r2 object put "multitifs/${r2_key}" --local \
      --file "$local_file" \
      --content-type "$content_type"
  fi
}

put_object static/polygons_new.geojson static/polygons_new.geojson application/geo+json
put_object static/polygons.geojson static/polygons.geojson application/geo+json
put_object static/favicon.svg static/favicon.svg image/svg+xml

echo "r2-seed-local: uploaded static/* to local R2 (multitifs)."
