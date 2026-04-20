# Dependency Updates with Renovate

## What is Renovate?

[Renovate](https://docs.renovatebot.com/) is a GitHub App that automatically creates
pull requests to keep dependencies up to date. It replaces Dependabot for this project
because it supports features we need that Dependabot lacks:

- **Lockfile-only updates** — update `uv.lock` without touching `pyproject.toml`,
  avoiding unnecessary lower-bound bumps that could cause conflicts downstream.
- **Grouped PRs** — enforce lockstep upgrades (e.g. pyats + genie in one PR).
- **Per-package update strategies** — different behavior for core framework packages
  vs. everything else.
- **Vulnerability-aware range bumps** — only bump `pyproject.toml` when a CVE requires it.

> **Note:** GitHub Dependabot *security alerts* (repo Settings → Security) remain enabled.
> Renovate reads those alerts via the GitHub API to trigger security PRs.

## Three-Tier Strategy

All configuration lives in [`renovate.json`](../renovate.json) at the repo root.

| Tier | Packages | What happens | `rangeStrategy` |
|------|----------|-------------|-----------------|
| **Track Latest** | `pyats`, `genie`, `robotframework`, `robotframework-pabot` | Always bump the `>=` lower bound in `pyproject.toml` + update `uv.lock` | `bump` |
| **Security** | Any package with a CVE | Bump `pyproject.toml` + update `uv.lock` | `bump` (via `vulnerabilityAlerts`) |
| **Routine** | Everything else | Only update `uv.lock`; `pyproject.toml` unchanged | `update-lockfile` |

### Why the distinction?

`nac-test` is consumed as a library/tool in environments with their own dependency
constraints (e.g. radkit-client, customer CI). Unnecessary lower-bound bumps in
`pyproject.toml` can trigger version conflicts in those environments. The *routine*
tier avoids this by only updating the lockfile — CI still tests against the latest
resolved versions, but `pyproject.toml` stays relaxed.

The *Track Latest* tier is for packages where we always want the newest release
(test frameworks, pyats/genie ecosystem) and are willing to accept the tighter bound.

## Grouping Rules

| Group | Packages | Why |
|-------|----------|-----|
| `pyats-genie` | `pyats`, `genie` | Must be upgraded in lockstep — mixed major.minor versions cause runtime errors |
| `github-actions` | All GitHub Actions | Reduce PR noise; SHA-pinned actions are low-risk to batch |

All other packages get individual PRs.

## Registry Override

The project's `pyproject.toml` uses an internal Cisco Artifactory index as the default
pip index. Renovate cannot access this registry, so a `registryUrls` rule redirects
all Python package lookups to `https://pypi.org/simple/`. Internal packages
(`nac-yaml`, `nac-test-pyats-common`) that are not on PyPI are disabled in the config.

## Other Settings

| Setting | Value | Reason |
|---------|-------|--------|
| `minimumReleaseAge` | 3 days | Avoid broken or yanked releases (skipped for Track Latest and security) |
| `osvVulnerabilityAlerts` | `true` | Supplements GitHub advisories with [OSV.dev](https://osv.dev/) data |
| `extends` | `config:recommended` | Includes sensible defaults: dependency dashboard, monorepo grouping, SHA-pinned actions |

## References

- [Renovate Docs](https://docs.renovatebot.com/)
- [pep621 manager](https://docs.renovatebot.com/modules/manager/pep621/)
- [GitHub issue #761](https://github.com/netascode/nac-test/issues/761) — original design discussion
