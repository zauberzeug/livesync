#!/usr/bin/env bash
. ~/assert.sh
set -e

# create source file
mkdir -p /root/my_project
echo 'file content' > /root/my_project/file.txt

# livesync should sync into a target path with spaces, also below the home directory, and run the on-change command there
cd /root/my_project
livesync --ssh-port 2222 --on-change 'touch "on change.txt"' . "target:~/with space/sub dir" &
sleep 5
assert_eq "file content" "$(cat '/target/with space/sub dir/file.txt')" "wrong file content"
assert_eq 1 "$(find '/target/with space/sub dir' -name 'on change.txt' | wc -l)" "on-change should have run in the target folder"

# change source file, livesync should update the target file
echo 'new file content' > file.txt
sleep 5
assert_eq "new file content" "$(cat '/target/with space/sub dir/file.txt')" "wrong file content"
