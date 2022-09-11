#/usr/bin/env bash
. ~/assert.sh
set -e

cd /root
mkdir -p my_project
cd my_project
echo 'file created' > file.txt
git config --global init.defaultBranch main
git config --global user.email "livesync@zauberzeug.com"
git config --global user.name "Zauberzeug"
git init
git add file.txt
git commit -m 'initial commit'
livesync --mutex-interval 1 target &
sleep 1
assert_eq "file created" "$(cat /target/my_project/file.txt)" "wrong file content"
echo 'file changed' > file.txt
sleep 1
assert_eq "file changed" "$(cat /target/my_project/file.txt)" "wrong file content"
sleep 1
assert_eq " M file.txt" "$(tail -n 1 /target/.livesync_mutex)" "wrong mutex description"
