#/usr/bin/env bash
. ~/assert.sh
set -e

# create source folder
mkdir -p /root/my_project
echo 'file content' > /root/my_project/file.txt

# create git repository
cd /root/my_project
git config --global init.defaultBranch main
git config --global user.email "livesync@zauberzeug.com"
git config --global user.name "Zauberzeug"
git init
git add file.txt
git commit -m 'initial commit'

# livesync should create the target file
livesync --target-port 2222 --mutex-interval 1 . target &
sleep 5
assert_eq "file content" "$(cat /target/my_project/file.txt)" "wrong file content"

# change source file, livesync should update the target file and write the git status to the mutex file
echo 'new file content' > /root/my_project/file.txt
sleep 5
assert_eq "new file content" "$(cat /target/my_project/file.txt)" "wrong file content"
assert_eq " M file.txt" "$(tail -n 2 /target/.livesync_mutex)" "wrong mutex description"
