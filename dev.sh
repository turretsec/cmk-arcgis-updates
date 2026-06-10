#!/usr/bin/env bash
# dev.sh - start dev environment, seed plugin files, start watcher

set -euo pipefail

echo "Starting container..."
docker compose up -d

echo "Waiting for site to initialize..."
until docker compose exec -T checkmk-dev \
    test -f /omd/sites/cmk/etc/omd/site.conf 2>/dev/null; do
    printf "."
    sleep 3
done
echo " ready!"

echo "Seeding plugin files..."
docker cp ./local/. "$(docker compose ps -q checkmk-dev)":/omd/sites/cmk/local/

echo "Starting file watcher..."
exec docker compose watch