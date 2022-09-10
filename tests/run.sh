#!/usr/bin/env bash
set -e

test(){
    rm -rf target/* target/.livesync_mutex
    NAME=${1%.*}
    UPPER=${NAME//_/ }
    echo; echo "=== $(echo $UPPER | tr '[:lower:]' '[:upper:]') ==="
    docker compose run --rm --entrypoint="bash -c" livesync "/livesync/tests/$1" && echo "--- OK ---" || echo "-- FAILED ---"
    rm -rf target/* target/.livesync_mutex
}

docker compose build
docker compose up -d target
sleep 3

test test_syncing_with_git_summary.sh
