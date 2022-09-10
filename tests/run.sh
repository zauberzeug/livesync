#!/usr/bin/env bash
test(){
    rm -rf target/* target/.livesync_mutex
    NAME=${1%.*}
    UPPER=${NAME//_/ }
    echo; echo "=== $(echo $UPPER | tr '[:lower:]' '[:upper:]') ==="
    docker compose run --rm --entrypoint="bash -c" livesync "/livesync/tests/$1"
    RESULT=$?
    rm -rf target/* target/.livesync_mutex
    [ $RESULT -eq 0 ] && echo "--- OK ---" || echo "-- FAILED ---"
    [ $RESULT -eq 0 ] || docker compose logs target
    [ $RESULT -eq 0 ] || exit 1
    return $RESULT
}

docker compose build
docker compose up -d target
sleep 3

test test_syncing_with_git_summary.sh
