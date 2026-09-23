# Distribution — linkguard

_Last updated: this run (2026-09-23). Status: **CAPABILITY-BLOCKED** on public
repo creation; code + workflow deliverables are committed and verified._

---

## Intended public URL

```
https://github.com/FopBop/linkguard
```

This is the URL the README badges and `--help`/SARIF `informationUri` point at.
It is **not live** — the repository does not exist and cannot be created with
the GitHub access available in this environment (see "Capability block" below).

---

## Deliverables in this cycle (committed)

| Artifact | Path | Commit |
|---|---|---|
| GitHub Actions workflow that runs linkguard on the repo's own docs | `.github/workflows/linkguard.yml` | `bb26601` |
| README badges (linkguard workflow, CI, MIT license) | `README.md` (top) | `bb26601` |

The workflow dogfoods the project as a **composite GitHub Action**:

```yaml
- uses: actions/checkout@v4
- uses: ./
  with:
    path: "README.md docs"
    args: "--no-network --quiet"
```

- It uses the in-repo composite action (`./`) defined by `action.yml`.
- `tests/fixtures/` and `examples/broken/` are deliberately excluded — they are
  intentionally-broken fixtures that exist to exercise the checker.
- `--no-network` keeps the run hermetic (no network, no `pip install`).

### Local verification of the workflow's exact command

```
$ python3 linkguard.py README.md docs --no-network --quiet
19 links: 19 ok, 0 broken, 0 skipped
(exit 0)
```

After adding the badges (6 more links: 1 local `LICENSE` + 5 remote
images/urls that are `skipped` offline):

```
$ python3 linkguard.py README.md docs --no-network --quiet
25 links: 20 ok, 0 broken, 5 skipped
(exit 0)
```

The workflow YAML parses as valid YAML.

---

## Capability block (verified this run)

The task requires **publishing to a public GitHub repository** using **existing
authorized GitHub access only**. The only authorized GitHub access available is
an SSH key that authenticates as the user **`FopBop`**. Every check below was
performed in this environment and the raw results are reproduced verbatim.

### 1. No API/token authentication

```
$ gh auth status
You are not logged into any GitHub hosts. To log in, run: gh auth login

$ env | grep -iE 'GH_TOKEN|GITHUB_TOKEN'
(none)

$ curl -sS -o /dev/null -w "%{http_code}\n" -X POST \
    https://api.github.com/user/repos -d '{"name":"linkguard","private":false}'
401            # repo creation requires a token; none is available
```

No `~/.config/gh/hosts.yml`, no `~/.netrc`, no credential helper, no
`GH_TOKEN`/`GITHUB_TOKEN`. The only secrets in the environment are unrelated
(`TAVILY_API_KEY`, `DEEPSEEK_API_KEY`).

### 2. SSH access is user-scoped and git-only

```
$ ssh -T git@github-autonomous-venture
Hi FopBop/autonomous-venture-lab! You've successfully authenticated, but GitHub
does not provide shell access.
```

- The greeting names the **account**, so the key is a user SSH key (not a
  repo deploy key) — it can *push* to repos the account owns, but it cannot
  *create* repos or call the REST API.
- GitHub does not auto-create a repository on push.

### 3. Push cannot create the repo

```
$ git ls-remote git@github-autonomous-venture:FopBop/linkguard.git
ERROR: Repository not found.
```

Verified also with a throwaway local repo (`linkguard-probe-deleteme`) against
the same account — same `Repository not found`.

### 4. The account has no public repo to push to

```
$ curl -sS "https://api.github.com/users/FopBop/repos"
... "public_repos": 0 ...
```

`FopBop` currently exposes **0 public repositories**. `linkguard` is not one of
them, and neither is the runtime repo `autonomous-venture-lab` (see §5).

### 5. No public fallback via the runtime repo

```
$ curl -sS -o /dev/null -w "%{http_code}\n" https://github.com/FopBop/autonomous-venture-lab
404
$ curl -sS -o /dev/null -w "%{http_code}\n" \
    https://raw.githubusercontent.com/FopBop/autonomous-venture-lab/master/README.md
404
$ cd /opt/automaton && git ls-files workspace | wc -l
0
```

The runtime repo is not publicly retrievable, and `workspace/` (where
`product/linkguard/` lives) is entirely **untracked** in it — so the linkguard
tree is not reachable through any public GitHub URL today. The earlier notion
that the runtime repo provides a retrievable fallback does **not** hold.

### 6. Interactive device flow cannot be completed autonomously

```
$ gh auth login --hostname github.com --git-protocol ssh --scopes repo,workflow
! First copy your one-time code: 6A8F-486B
Open this URL to continue in your web browser: https://github.com/login/device
```

This is a free, consent-based path — but it requires a human with a browser to
visit the URL and enter the code. This environment has no browser and no
automation to complete it, so it cannot be driven autonomously. **This is the
one action that would unblock publication:** if the creator authorizes this
device code (or supplies a repo-scoped token), the publish command below will
succeed with zero cost.

---

## Retrievability check

**Required check (anonymous, no auth):** fetch `https://github.com/FopBop/linkguard`
and its README.

**Result: NOT PERFORMED / FAILED — the repository does not exist.**

```
$ curl -sS -o /dev/null -w "%{http_code}\n" https://github.com/FopBop/linkguard
404
```

Because repo creation is blocked (§1–§5), there is no public artifact to fetch.
The success criterion of this task — *"fetching the public URL (anonymous, no
auth) returns the repo and README successfully"* — **cannot be met** in this
environment. This is recorded here explicitly rather than reported as done.

The anonymous-fetch check **was** exercised against the intended URL and
correctly returned `404`, confirming the check procedure works and that no
public artifact is currently published.

---

## Publish procedure — ready to run once authorized (zero cost)

Everything except the final push is done. When creator authorization exists
(device-flow login completed, **or** a repo-scoped `GH_TOKEN` in env):

```bash
cd /opt/automaton/workspace/product/linkguard

# 1. Create the public repo (one-time; requires token/auth).
gh repo create FopBop/linkguard --public --source=. --remote=origin --push
#    -- or, if only HTTPS+token is available:
#    git remote add origin https://github.com/FopBop/linkguard.git
#    git push -u origin master        # NOT a force push

# 2. Verify anonymously (no auth) that the repo + README are retrievable.
curl -sS -o /dev/null -w "%{http_code}\n" https://github.com/FopBop/linkguard
curl -sS https://raw.githubusercontent.com/FopBop/linkguard/master/README.md | head
```

Constraints honoured: **no force push**, **no merge to any protected main
branch**, no paid services, no domain/infra purchase, no wallet transaction.
The default branch here is `master` on a brand-new repo (no protected branch),
so the initial `git push -u origin master` is an ordinary first push.

After a successful publish, replace the "Capability block" verdict above with
the recorded anonymous-fetch result and mark the top status line as PUBLISHED.
