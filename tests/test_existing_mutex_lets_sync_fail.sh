. ~/assert.sh

# create and enter source folder
mkdir -p /root/my_project
cd /root/my_project

# fill mutex with some other user, so that livesync fails (`timeout` yields code 1, i.e. no timeout)
echo "some_user $(date -u +'%Y-%m-%dT%H:%M:%S.%6N')" > /target/.livesync_mutex
cat /target/.livesync_mutex
timeout 5 livesync --target-port 2222 --mutex-interval 1 target
assert_eq 1 $? "livesync should fail" || exit 1

# fill mutex with same user, so that livesync succeeds (`timeout` yields code 124, i.e. timeout)
echo "$HOSTNAME $(date -u +'%Y-%m-%dT%H:%M:%S.%6N')" > /target/.livesync_mutex
cat /target/.livesync_mutex
timeout 5 livesync --target-port 2222 --mutex-interval 1 target
assert_eq 124 $? "livesync should start" || exit 1
