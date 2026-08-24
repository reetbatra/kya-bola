#!/usr/bin/env bash
# Fetch India ADM1/ADM2 boundaries from geoBoundaries (gbOpen, ODbL 1.0).
#
# Use the per-country gbOpen files, never the CGAZ composite: CGAZ follows US
# State Department definitions for disputed areas, which do not match India's
# official boundary.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data
for LEVEL in ADM1 ADM2; do
  URL=$(curl -s "https://www.geoboundaries.org/api/current/gbOpen/IND/${LEVEL}/" \
        | python3 -c "import json,sys; d=json.load(sys.stdin); d=d[0] if isinstance(d,list) else d; print(d['simplifiedGeometryGeoJSON'])")
  OUT="data/ind_$(echo "$LEVEL" | tr 'A-Z' 'a-z')_simplified.geojson"
  echo "fetching $LEVEL -> $OUT"
  curl -sL "$URL" -o "$OUT"
done
echo "done. now run: uv run python -m harness.crosswalk"
