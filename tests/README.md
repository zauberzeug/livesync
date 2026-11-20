# Testing

For testing we use two containers managed by docker-compose.
Because they are in the same network, they can reach each other by their name.
The `target` has an SSH server running and mounted the repository's `tests/target` dir into `/root`.
In `source` we have installed the local LiveSync code and also mounted the `tests/target`.
But here it is located in `/target`.
Thereby we can create folders and files in `source`, start LiveSync with `target` and then simply test if they appear in `/target`.
All is running in a linear script on `source`.

These tests are written in Bash and must start with `test_*`.
For assertions the [assert.sh](https://github.com/torokmark/assert.sh) library is provided.

`run.sh` generates a throwaway SSH key pair in `tests/.ssh` on its first run and authorizes it on the `target`.
Both are ignored by git and kept out of the Docker image; delete `tests/.ssh` to get a new pair.

To run only some of the tests, pass their file names in `TESTS`, e.g. `TESTS=test_target_path.sh ./run.sh`.
