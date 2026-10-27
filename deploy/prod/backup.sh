#!/usr/bin/env bash
# Nightly full backup (cron, 02:00 IST). Same zip layout as snapshot_export.ps1, so
# snapshot_restore.ps1 can load a production backup onto a dev laptop.
# Stops the stack for ~1-2 minutes so Postgres, Neo4j and Chroma are copied consistently.
set -euo pipefail
APP=/home/ubuntu/djsce-brain
OUT=/home/ubuntu/backups
KEEP=14
stamp=$(date +%Y%m%d-%H%M)
work=$(mktemp -d)
trap 'rm -rf "$work"; cd "$APP" && docker compose up -d >/dev/null 2>&1 || true' EXIT

mkdir -p "$OUT"
cd "$APP"
printf 'created: %s\ngit_commit: %s\nvolumes: pgdata, neo4jdata, chromadata\n' \
  "$(date -Iseconds)" "$(cat REVISION 2>/dev/null || echo unknown)" > "$work/manifest.txt"
docker compose stop >/dev/null
for v in pgdata neo4jdata chromadata; do
  docker run --rm -v "djsce-brain_${v}:/v:ro" -v "$work:/out" alpine tar czf "/out/${v}.tgz" -C /v .
done
docker compose up -d >/dev/null
(cd "$work" && zip -q "$OUT/djsce-brain-snapshot-$stamp.zip" manifest.txt pgdata.tgz neo4jdata.tgz chromadata.tgz)
ls -1t "$OUT"/djsce-brain-snapshot-*.zip | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "backup ok: $OUT/djsce-brain-snapshot-$stamp.zip"
