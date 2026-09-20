# Example: broken

This example deliberately contains a **known-broken local link** so
`python3 linkguard.py examples/broken --no-network` demonstrates exit code `1`.

- This target does not exist: [Missing local file](./does-not-exist.md)
- This anchor does not exist: [Missing anchor](#no-such-heading)

See `linkguard.cfg` in this directory for the ignore-rule example.
