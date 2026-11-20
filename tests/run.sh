#!/usr/bin/env bash

[[ $GITHUB_ACTION ]] && SUDO="sudo"

cleanup(){
    eval "$SUDO" rm -rf target/* target/.livesync_mutex
    sleep 0.5
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
    [ $RESULT -eq 0 ] && echo "--- OK ---" || echo "--- FAILED ---"
    #[ $RESULT -eq 0 ] || docker compose logs target
    [ $RESULT -eq 0 ] || exit 1
    return $RESULT
}

# generate a throwaway SSH key pair for the test containers instead of committing one
if [ ! -f .ssh/id_ed25519 ]; then
    mkdir -p .ssh
    ssh-keygen -q -t ed25519 -N '' -C livesync.docker -f .ssh/id_ed25519 || exit 1
fi
# always (re-)authorize the key on the target, so a missing or stale authorized_keys cannot break the tests
mkdir -p target/.ssh
eval "$SUDO" cp .ssh/id_ed25519.pub target/.ssh/authorized_keys || exit 1

docker compose build || exit 1
docker compose up -d target
sleep 3

for i in test_*.sh; do
    test $i
done

docker compose down
