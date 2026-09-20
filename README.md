# linkguard

> [PLACEHOLDER] Zero-dependency Markdown link & asset health checker + repo-safe
> CI gate. Single-file CLI, GitHub Action wrapper, no `pip install`, no Node,
> no paid services.

**Status:** v1 scaffold (interfaces defined, feature bodies not yet
implemented — see `ARCHITECTURE_v1.md` section 7 for the build order).

---

This README is a placeholder heading for the scaffold build step. It will be
replaced with the full landing page (install, usage, real command output, CI
snippet) in the "Examples + docs" step of the build order.

## Quick start (once the features land)

```console
$ python3 linkguard.py . --no-network
```

`--no-network` is the recommended default: it validates local file targets and
intra-document anchors offline and reports remote URLs as `skipped`.

## Exit codes

| Code | Meaning                                              |
|------|------------------------------------------------------|
| `0`  | All checked links OK (skips allowed).                |
| `1`  | At least one `broken` finding.                       |
| `2`  | Usage error, unreadable file, or invalid config.     |

## License

MIT — see [LICENSE](LICENSE).
