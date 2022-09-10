. ~/assert.sh
cd /root
mkdir -p my_project
cd my_project
echo "some_user $(date -u +'%Y-%m-%dT%H:%M:%S.%6N')" > /target/.livesync_mutex
cat /target/.livesync_mutex
timeout 2 livesync --source . --mutex-interval 1 target
assert_eq 1 $? "livesync should fail" || exit 1 # livesync fails with exit code 1, timeout with 124
echo "$HOSTNAME $(date -u +'%Y-%m-%dT%H:%M:%S.%6N')" > /target/.livesync_mutex
cat /target/.livesync_mutex
timeout 2 livesync --source . --mutex-interval 1 target
assert_eq 124 $? "livesync should start because its the same user" || exit 1 # livesync fails with exit code 1, timeout with 124
