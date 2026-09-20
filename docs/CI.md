# linkguard — CI usage (GitHub Action)

> **Status:** v1 scaffold. The `action.yml` wrapper is present and matches the
> contracted interface (ARCHITECTURE_v1.md §3.5); it runs the CLI which is
> still a stub until the feature build order (§7) lands.

linkguard ships as a **composite** GitHub Action with **no dependency install
step** (the CLI is standard-library-only Python). It fails the job with exit
code `1` when any link is broken.

## One-line usage

```yaml
- uses: OWNER/linkguard@v1
  with:
    path: .
    args: --no-network          # offline-safe default for most docs repos
```

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `path` | no | `.` | File or directory to scan. |
| `args` | no | `""` | Extra CLI arguments (e.g. `--no-network --sarif --output linkguard.sarif`). |

## Full workflow example (offline + SARIF upload)

```yaml
name: linkguard
on: [push, pull_request]
jobs:
  check-links:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: OWNER/linkguard@v1
        with:
          path: .
          args: --no-network --sarif --output linkguard.sarif
      - name: Upload SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: linkguard.sarif
```

GitHub-hosted runners and the `actions/*` helpers used here are free for
public repositories. linkguard itself requires no network for the offline
(`--no-network`) path, so the check is fast and hermetic.
