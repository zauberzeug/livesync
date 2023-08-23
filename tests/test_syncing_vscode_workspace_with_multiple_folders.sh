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
sleep 5
assert_eq "file created" "$(cat /target/my_project/file.txt)" "wrong file content"
echo 'file changed' > ../another_project/data.txt
echo 'file changed' > file.txt
sleep 5
assert_eq "file changed" "$(cat /target/my_project/file.txt)" "wrong file content"
assert_eq "file changed" "$(cat /target/another_project/data.txt)" "wrong data content"