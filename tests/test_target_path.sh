. ~/assert.sh
set -e

# create source file
mkdir -p /root/my_project
echo 'file content' > /root/my_project/file.txt

# livesync should create the target file and run the on-change command
cd /root/my_project
livesync --ssh-port 2222 . target:foo/bar &
sleep 5
assert_eq "file content" "$(cat /target/foo/bar/file.txt)" "wrong file content"

# change source file, livesync should update the target file and run the on-change command again
echo 'new file content' > file.txt
sleep 5
assert_eq "new file content" "$(cat /target/foo/bar/file.txt)" "wrong file content"
