. ~/assert.sh
set -e

cd /root
mkdir -p my_project
mkdir -p another_project
echo 'file created' > another_project/data.txt
cd my_project
echo 'file created' > file.txt
echo '{
  "folders": [ { "path": "." }, { "path": "../another_project" }]}' > my_project.code-workspace
livesync target &
ls -lha
sleep 1
assert_eq "file created" "$(cat /target/my_project/file.txt)" "wrong content in file.txt"
echo 'file changed' > ../another_project/data.txt
echo 'file changed' > file.txt
sleep 1
ls -lha
assert_eq "file changed" "$(cat /target/my_project/file.txt)" "wrong content in file.txt"
assert_eq "file changed" "$(cat /target/another_project/data.txt)" "wrong content in data.txt"