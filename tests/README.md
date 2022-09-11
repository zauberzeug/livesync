# Testing

For testing we use two containers managed by docker-compose.
Because they are in the same network they can reach each other by their name.
The `target` has an ssh server running and mounted the repositories `tests/target` dir into `/root`.
In `source` we have installed the local livesync code and also mounted the `tests/target`. But here its located in `/target`.
Thereby we can create folders in files in source, start livesync with `target` as target and then simply test if they appear in `/target` on `source`.

Tests are written in bash and must start with `test_*`.
For assertions the [assert.sh](https://github.com/torokmark/assert.sh) lib is provided.
