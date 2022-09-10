. ~/assert.sh
set -e

cd /root
mkdir -p my_project
cd my_project
echo 'file created' > file.txt
livesync --source . --mutex-interval 1 target &
sleep 1
assert_eq "file created" "$(cat /target/my_project/file.txt)" "wrong file content"
echo 'file changed' > file.txt
sleep 1
assert_eq "file changed" "$(cat /target/my_project/file.txt)" "wrong file content"