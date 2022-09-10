#!/usr/bin/env bash

cleanup(){
    sudo rm -rf target/* target/.livesync_mutex
}

test(){
    cleanup
    NAME=${1%.*}
    UPPER=${NAME//_/ }
    echo; echo "=== $(echo $UPPER | tr '[:lower:]' '[:upper:]') ==="
    docker compose run --rm --entrypoint="bash -c" livesync "/livesync/tests/$1"
    RESULT=$?
    cleanup
    [ $RESULT -eq 0 ] && echo "--- OK ---" || echo "-- FAILED ---"
    [ $RESULT -eq 0 ] || docker compose logs target
    [ $RESULT -eq 0 ] || exit 1
    return $RESULT
}

docker compose build
docker compose up -d target
sleep 3
docker compose ps

docker compose run --rm --entrypoint="bash -c" livesync "ssh target 'ls'"

test test_syncing_with_git_summary.sh
test test_syncing_plain_directory.sh
test test_existing_mutex_lets_sync_fail.sh
