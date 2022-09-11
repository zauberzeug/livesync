. ~/assert.sh
set -e

cd /root
mkdir -p my_project
cd my_project
mkdir -p /target/my_project/
touch /target/my_project/file.txt
livesync target &
sleep 1
assert_eq 0 "$(find /target -name '*txt' | wc -l)" "file on target should have been deleted, because its not present in source"
