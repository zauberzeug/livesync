#!/usr/bin/env bash

cleanup(){
    [[ $GITHUB_ACTION ]] && SUDO="sudo"
    eval "$SUDO" rm -rf target/* target/.livesync_mutex
}

test(){
    cleanup
    NAME=${1%.*}
    UPPER=${NAME//_/ }
    echo
    echo "=== $(echo $UPPER | tr '[:lower:]' '[:upper:]') ==="
    docker compose run --entrypoint="bash -c /livesync/tests/$1" --rm livesync
    RESULT=$?
    cleanup
    [ $RESULT -eq 0 ] && echo "--- OK ---" || echo "-- FAILED ---"
    #[ $RESULT -eq 0 ] || docker compose logs target
    [ $RESULT -eq 0 ] || exit 1
    return $RESULT
}

docker compose build
docker compose up -d target
sleep 3

for i in test_*.sh; do
    test $i
done

docker compose down
