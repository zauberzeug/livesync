# Security Policy

## Supported versions

Only the latest version of LiveSync receives security fixes.

## Scope

LiveSync runs `rsync` and `ssh` on your machine and commands on the target system, with the permissions of the SSH user you configure.
Some of this is by design and not a vulnerability:

- The `--on-change` command (`on_change` in Python) runs on the target exactly as given.
- Anyone who can write to the source folder decides what is copied to the target, and a `.syncignore` in the source folder decides what is skipped.

A vulnerability is, for example, a path, pattern or summary text that makes LiveSync run a command the user did not configure, or a way to write outside the configured target folder.

## Reporting a vulnerability

Please do not open a public issue.
Instead, report it privately via [GitHub → Security → Report a vulnerability](https://github.com/zauberzeug/livesync/security/advisories/new).
Include the LiveSync version, your configuration and the steps to reproduce.
