. ~/assert.sh
set -e

cd /root
mkdir -p my_project
cd my_project
echo 'file created' > file.txt
livesync --source . --on-change "mktemp ../onchange-XXXXXXXX" target &
sleep 1
assert_eq "file created" "$(cat /target/my_project/file.txt)" "wrong file content"
echo 'new file content' > file.txt
assert_eq 1 "$(find /target -name 'onchange-*' | wc -l)" "on-change should have been called once on init"
sleep 1
assert_eq "new file content" "$(cat /target/my_project/file.txt)" "wrong file content"
assert_eq 2 "$(find /target -name 'onchange-*' | wc -l)" "on-change should have been called two times"
