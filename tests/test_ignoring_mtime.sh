. ~/assert.sh
set -e

cd /root
mkdir -p /target/my_project
touch /target/my_project/file.txt
mkdir -p my_project
cd my_project
sleep 2
touch file.txt
livesync target &
sleep 5
assert_gt $(stat -c %Y file.txt) $(stat -c %Y /target/my_project/file.txt) "mtime should be different"