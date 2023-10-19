. ~/assert.sh
set -e

# create source folders and file
mkdir -p /root/project1
mkdir -p /root/project2
echo 'file content 1' > /root/project1/file.txt
echo 'file content 2' > /root/project2/file.txt

# create workspace file
echo '
  {
    "folders": [
      { "path": "." },
      { "path": "../project2" }
    ]
  }
' > /root/project1/project1.code-workspace

# livesync should create the target files
cd /root/project1
livesync --target-port 2222 project1.code-workspace target &
sleep 5
assert_eq "file content 1" "$(cat /target/project1/file.txt)" "wrong file content"
assert_eq "file content 2" "$(cat /target/project2/file.txt)" "wrong file content"

# change source file, livesync should update the target files
echo 'new file content 1' > /root/project1/file.txt
echo 'new file content 2' > /root/project2/file.txt
sleep 5
assert_eq "new file content 1" "$(cat /target/project1/file.txt)" "wrong file content"
assert_eq "new file content 2" "$(cat /target/project2/file.txt)" "wrong file content"
