. ~/assert.sh
set -e

# create target file
mkdir -p /target/my_project
touch /target/my_project/file.txt

# create newer source file
sleep 2
mkdir -p /root/my_project
touch /root/my_project/file.txt

# livesync should not overwrite the target file just because it is older
cd /root/my_project
livesync --ssh-port 2222 . target &
sleep 5
assert_gt $(stat -c %Y file.txt) $(stat -c %Y /target/my_project/file.txt) "mtime should be different"
