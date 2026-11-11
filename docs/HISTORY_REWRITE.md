# History rewrite — remove local dev paths (runbook)

Status: **prepared, not executed.** The public tree is already clean
(`chore(privacy)` commit); this procedure removes the old strings from
past commits before the repository is made public.

## What it changes

- Rewrites **file contents** in every commit that contained the developer's
  Windows profile path or the local checkout path.
- Does **not** change author/committer names, emails or dates.
- Rewrites every commit hash from the first affected commit onward and
  moves all tags (`v1.0.0` … `v1.3.1`).
- No secrets are involved (only a username and local folder names).

## Prerequisites

- `git-filter-repo` (single script is enough):
  `python git-filter-repo.py --version`
- A **backup bundle** of the current history (keep it outside the repo):
  `git bundle create <backup>.bundle --all`
- A replacement map **outside the repo** (it contains the literal strings
  on purpose; never commit it). Categories:
  1. full system-Python path → `python`
  2. project `.venv` Python path → `<repo>\.venv\Scripts\python.exe`
  3. local checkout root (plain and Python-escaped forms) → `<repo>`
  4. Windows profile root (plain and Python-escaped forms) → the same
     root with a `<user>` placeholder instead of the account name
  5. any remaining bare username token → `<user>`

## Procedure (dry run first)

```bat
git bundle create <backup>.bundle --all
git clone --no-hardlinks <repo> rewrite
cd rewrite
git remote remove origin
python <path>\git-filter-repo.py --replace-text <map>.txt --force
```

Verify **before** touching the remote:

```bat
git rev-list --all --count          :: must match the original main count (154)
git tag                             :: all release tags present
git diff --stat <old-main> HEAD     :: must be empty (HEAD content unchanged)
```

Then scan every rewritten commit (must print nothing):

```bat
$shas = git rev-list --all
foreach ($s in $shas) { git grep -n -I -E "<profile>|<checkout>" $s }
```

Run the fast suite in the rewritten clone and the no-leak gate:

```bat
python -m pytest tests -q -p no:cacheprovider --no-cov -m "not slow" -n auto
python -c "import tools.quality_metrics as q; print(q._no_leak_scan())"
```

## Publish (only with explicit approval)

```bat
git push --force-with-lease origin main
git push --force --tags origin
```

## Aftermath

- Every collaborator/CI clone must be re-cloned (old hashes are gone).
- Open PRs/forks based on old commits become invalid.
- GitHub may keep old commits reachable by SHA for a while; for a
  username/local-path leak this is acceptable. If real secrets ever leak,
  rotate them and contact GitHub support to purge cached views.
- Re-check the release assets/checksums and tag targets after the push.

## Rollback

```bat
git clone <backup>.bundle restored
cd restored
git push --force-with-lease origin main
git push --force --tags origin
```

The backup bundle is the source of truth until the new history is verified.
