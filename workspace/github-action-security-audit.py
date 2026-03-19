# GitHub Actions Security Audit

**Repositories:** netascode/nac-test · netascode/nac-test-pyats-common
**Date:** 2026-03-16
**Scope:** `.github/workflows/test.yml`, `.github/workflows/release.yml` (both repos)

Prompted by recent supply chain attacks targeting GitHub repositories through
compromised Actions. Both repositories share the same workflow template — all
findings apply to both unless explicitly noted otherwise. Findings are listed
by severity, followed by a per-repo remediation checklist.

---

## Repo comparison

| Aspect | `nac-test` | `nac-test-pyats-common` |
|---|---|---|
| `release.yml` | identical | identical |
| `actions/upload-artifact` | `@v7` (still not SHA-pinned) | `@v6` |
| `test` job timeout | 15 min | 10 min |
| Additional `test-windows` job | ✅ runs on `windows-latest` | ❌ |
| Extra push branch | + `release/pyats-integration-v1.1-beta` (temporary) | `main` only |
| Critical security findings | all apply | all apply |

All findings below apply to **both repos** unless marked with
`(nac-test-pyats-common only)` or `(nac-test only)`.

---

## 🔴 Critical

### 1. Unpinned third-party action — `qsnyder/action-wxt@master`

**File:** `test.yml` — `notification` job — **both repos**

Using `@master` instead of a pinned commit SHA is the most dangerous pattern
identified. If the upstream repository is ever compromised, malicious code
would execute immediately in our pipeline with direct access to `WEBEX_TOKEN`
and `WEBEX_ROOM_ID`.

**Fix:** pin to the current HEAD commit SHA and keep the branch as a comment
so Dependabot can track it:

```yaml
uses: qsnyder/action-wxt@ea6ec7075c508a0e39826c2c67173b5de1ace0e2  # master
```

> ⚠️ `qsnyder/action-wxt` has no versioned releases — only a `master` branch.
> Dependabot cannot track this meaningfully. Consider replacing it with a more
> actively maintained Webex notification action.

---

### 2. Script injection via user-controlled context values

**File:** `test.yml` — `notification` job, `Webex Notification` step — **both repos**

The Webex message inlines user-controlled context values directly into an
action input:

```yaml
MESSAGE: |
  * Commit: [${{ github.event.head_commit.message }}](...)
  * Author: ${{ github.event.sender.login }}
```

`github.event.head_commit.message` and `github.event.pull_request.title` are
fully attacker-controlled. A crafted commit message or PR title can inject
arbitrary content into messages sent to Webex.

**Fix:** write untrusted values to `$GITHUB_ENV` first and reference the env
var — never interpolate `github.event.*` directly into action inputs:

```yaml
- name: Prepare notification vars
  run: |
    echo "COMMIT_MSG=${{ github.event.head_commit.message }}" >> $GITHUB_ENV
    echo "PR_TITLE=${{ github.event.pull_request.title }}" >> $GITHUB_ENV

- name: Webex Notification
  uses: qsnyder/action-wxt@ea6ec7075c508a0e39826c2c67173b5de1ace0e2  # master
  env:
    TOKEN: ${{ secrets.WEBEX_TOKEN }}
    ROOMID: ${{ secrets.WEBEX_ROOM_ID }}
    MESSAGE: |
      * Commit: [${{ env.COMMIT_MSG }}](...)
      * Author: ${{ github.event.sender.login }}
```

---

### 3. Missing `permissions:` blocks — `security` and `test` jobs

**File:** `test.yml` — **both repos**

Both jobs omit a `permissions:` block. GitHub's default when no block is
specified is `write` on all scopes, violating the principle of least privilege.

`nac-test` also has a `test-windows` job with the same issue.

**Fix:**

```yaml
security:
  permissions:
    contents: read

test:
  permissions:
    contents: read

test-windows:        # nac-test only
  permissions:
    contents: read
```

---

### 4. Missing `permissions:` block — `release.yml`

**File:** `release.yml` — **both repos** (files are identical)

The build and publish job has no explicit permissions block, giving it implicit
write access to the entire repository. Only read access is needed.

**Fix:**

```yaml
build:
  permissions:
    contents: read
```

---

## 🟠 High

### 5. Third-party actions pinned to mutable version tags, not commit SHAs

**Files:** `test.yml`, `release.yml` — **both repos**

The following actions use version tags which can be silently updated by the
upstream author. Adding the version as a comment allows Dependabot to continue
tracking updates automatically.

| Action | `nac-test` | `nac-test-pyats-common` | Pinned SHA | Comment |
|---|---|---|---|---|
| `astral-sh/setup-uv` | `@v7` | `@v7` | `d0cc045d04ccac9d8b7881df0226f9e82c39688e` | `# v7` |
| `pre-commit/action` | `@v3.0.1` | `@v3.0.1` | `2c7b3805fd2a0fd8c1884dcaebf91fc102a13ecd` | `# v3.0.1` |
| `actions/checkout` | `@v6` ⚠️ | `@v6` ⚠️ | `11bd71901bbe5b1630ceea73d27597364c9af683` | `# v4` |
| `actions/upload-artifact` | `@v7` | `@v6` ⚠️ | `ea165f8d65b6e75b540449e92b4886f43607fa02` | `# v4` |

> ⚠️ `actions/checkout@v6` and `actions/upload-artifact@v6` reference
> non-existent versions — the current stable is `v4`. This appears to be a
> copy-paste error and should be corrected at the same time.

> ℹ️ With the `# vX` comment in place, the existing `dependabot.yml`
> (`package-ecosystem: github-actions`, daily schedule) will automatically
> open PRs to update both the SHA and the comment whenever a new version is
> released.

---

## 🔵 Low / Process

### 6. `release.yml` is not gated on passing tests

**File:** `release.yml` — **both repos** (files are identical)

A release can be published by pushing a tag to any commit, regardless of
whether tests pass. This risks publishing a broken package.

**Fix:** add `workflow_call` as a trigger to `test.yml` (one line), suppress
the notification job when called externally, and call it from `release.yml`
with a `needs:` dependency on the result.

**`test.yml` changes (minimal):**

```yaml
on:
  workflow_dispatch:
  pull_request:
  push:
    branches:
      - main
  workflow_call:        # ← add this trigger

# In the notification job, suppress when called from another workflow:
notification:
  if: always() && github.event_name != 'pull_request' && github.event_name != 'workflow_call'
```

**`release.yml` change:**

```yaml
jobs:
  test:
    uses: ./.github/workflows/test.yml   # runs the full test matrix
                                         # (incl. test-windows in nac-test)

  build:
    needs: test                           # publish only if all tests pass
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4
      - uses: astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e  # v7
      - name: Build and publish
        env:
          UV_PUBLISH_TOKEN: ${{ secrets.UV_PUBLISH_TOKEN }}
        run: |
          uv build
          uv publish
```

This keeps the existing tag-based release trigger (`on: push: tags: v*`) while
ensuring no package is published from a commit where tests did not pass.

---

## Fork / external contributor threat model

This is documented for completeness, as it is a common source of confusion.
Applies to both repos.

| Attack vector | Risk | Reason |
|---|---|---|
| Fork contributor pushing a release tag | ✅ None | Cannot push tags to upstream repo without write access |
| Fork PR reading `WEBEX_TOKEN` / `WEBEX_ROOM_ID` | ✅ None | `pull_request` trigger withholds secrets from fork workflows |
| Fork PR reading `UV_PUBLISH_TOKEN` | ✅ None | `release.yml` only triggers on tag push to upstream |
| Fork PR abusing `contents: write` in lint job | ✅ None | GitHub overrides to read-only for fork PRs; actor check provides additional guard |
| Changing `pull_request` → `pull_request_target` | 🔴 High | Would immediately expose all secrets to fork PRs — **never do this without fully understanding the implications** |

---

## What's already good

Applies to both repos unless noted.

- ✅ Timeouts on all jobs (prevents hung runners)
- ✅ Bandit security scanning with artifact upload
- ✅ No self-hosted runners on a public repo
- ✅ Fork PR protection in dependabot lock-file logic (`github.actor == 'dependabot[bot]' && ...full_name == github.repository`)
- ✅ `push` trigger on `test.yml` scoped to `main` only (+ temporary feature branch in `nac-test`)
- ✅ Dependabot configured for both `github-actions` and `pip` ecosystems
- ✅ Windows test coverage (`nac-test` only)

---

## Remediation checklist

Both repos share the same fixes. Apply independently to each.

### `nac-test`

- [ ] **#1** Pin `qsnyder/action-wxt` to commit SHA (`ea6ec70`) — consider replacing with maintained alternative
- [ ] **#2** Sanitize user-controlled context vars before passing to action inputs
- [ ] **#3** Add `permissions: contents: read` to `security`, `test`, and `test-windows` jobs in `test.yml`
- [ ] **#4** Add `permissions: contents: read` to `build` job in `release.yml`
- [ ] **#5** Pin `astral-sh/setup-uv`, `pre-commit/action`, `actions/checkout` to commit SHAs with version comments; correct `@v6` → `@v4` for `actions/checkout`; pin `actions/upload-artifact@v7` to SHA
- [ ] **#6** Add `workflow_call` trigger to `test.yml`; make `release.yml` `build` job depend on `test` via `needs:`

### `nac-test-pyats-common`

- [ ] **#1** Pin `qsnyder/action-wxt` to commit SHA (`ea6ec70`) — consider replacing with maintained alternative
- [ ] **#2** Sanitize user-controlled context vars before passing to action inputs
- [ ] **#3** Add `permissions: contents: read` to `security` and `test` jobs in `test.yml`
- [ ] **#4** Add `permissions: contents: read` to `build` job in `release.yml`
- [ ] **#5** Pin `astral-sh/setup-uv`, `pre-commit/action`, `actions/checkout`, and `actions/upload-artifact` to commit SHAs with version comments; correct `@v6` → `@v4` for first-party actions
- [ ] **#6** Add `workflow_call` trigger to `test.yml`; make `release.yml` `build` job depend on `test` via `needs:`
