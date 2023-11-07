. ~/assert.sh
set -e

# create source folder
mkdir -p /root/my_project

# create target file
mkdir -p /target/my_project/
touch /target/my_project/file.txt

# livesync should delete the target file, because it is not present in source
cd /root/my_project
livesync --ssh-port 2222 . target &
sleep 5
assert_eq 0 "$(find /target -name '*.txt' | wc -l)" "target file should have been deleted"
