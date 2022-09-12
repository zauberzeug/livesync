# Testing

For testing we use two containers managed by docker-compose.
Because they are in the same network, they can reach each other by their name.
The `target` has an SSH server running and mounted the repositories `tests/target` dir into `/root`.
In `source` we have installed the local livesync code and also mounted the `tests/target`.
But here it is located in `/target`.
Thereby we can create folders and files in `source`, start livesync with `target` and then simply test if they appear in `/target`.
All is running in a linear script on `source`.

These tests are written in Bash and must start with `test_*`.
For assertions the [assert.sh](https://github.com/torokmark/assert.sh) library is provided.
