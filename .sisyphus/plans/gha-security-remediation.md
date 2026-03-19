# GitHub Actions Security Remediation

## TL;DR

> **Quick Summary**: Implement 6 security audit findings in GitHub Actions workflows: pin actions to SHA, add permissions blocks, replace unmaintained Webex action with curl, sanitize user inputs, and gate releases on passing tests.
> 
> **Deliverables**: 
> - Hardened `.github/workflows/test.yml` with SHA-pinned actions, permissions blocks, sanitized inputs, and curl-based notifications
> - Hardened `.github/workflows/release.yml` with SHA-pinned actions, permissions block, and test gating
> 
> **Estimated Effort**: Short (2-3 hours)
> **Parallel Execution**: YES - 2 waves (3 parallel tasks, then 1 integration task)
> **Critical Path**: Task 1 → Task 4

---

## Context

### Original Request
User requested implementation of security audit findings from `workspace/github-action-security-audit.py` for the nac-test repository.

### Interview Summary
**Key Discussions**:
- Scope: nac-test only (nac-test-pyats-common separate plan later)
- Webex: Replace `qsnyder/action-wxt@master` with direct curl API call
- Release gating: Include in plan (Finding #6)
- Error handling: Log warning on curl failure, don't fail workflow

**Research Findings**:
- Audit SHA pins were outdated for 3/5 actions — verified current SHAs
- `actions/checkout@v6` exists (audit incorrectly claimed it doesn't)
- Webex API: `POST https://webexapis.com/v1/messages` with Bearer token

### Metis Review
**Identified Gaps** (addressed):
- notification job needs `permissions: {}` — added to scope
- JSON escaping for commit messages — use `jq -Rs`
- workflow_call condition in notification job — update `if` condition
- Empty commit message handling — ensure sanitization handles empty strings

---

## Work Objectives

### Core Objective
Harden GitHub Actions workflows by implementing all 6 security audit findings: pin actions to commit SHAs, add least-privilege permissions, remove vulnerable third-party action, sanitize user-controlled inputs, and gate releases on passing tests.

### Concrete Deliverables
- `.github/workflows/test.yml` — SHA-pinned actions, permissions blocks on `security`/`test`/`notification` jobs, curl-based Webex notification with sanitized inputs, `workflow_call` trigger
- `.github/workflows/release.yml` — SHA-pinned actions, permissions block on `build` job, `test` job calling test.yml with `needs:` dependency

### Definition of Done
- [ ] `grep -c 'qsnyder' .github/workflows/test.yml` returns `0` (qsnyder/action-wxt removed)
- [ ] `grep -cE '@[a-f0-9]{40}' .github/workflows/test.yml` returns ≥6 (all actions SHA-pinned)
- [ ] `grep -cE '@[a-f0-9]{40}' .github/workflows/release.yml` returns ≥2 (all actions SHA-pinned)
- [ ] `python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"` succeeds (valid YAML)
- [ ] `python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"` succeeds (valid YAML)
- [ ] `grep 'workflow_call' .github/workflows/test.yml` returns match
- [ ] `grep 'needs:.*test' .github/workflows/release.yml` returns match

### Must Have
- All 4 third-party actions pinned to commit SHAs with `# vX.Y.Z` comments
- `permissions: contents: read` on `security` and `test` jobs
- `permissions: {}` on `notification` job
- `permissions: contents: read` on `build` job in release.yml
- User-controlled context vars (`github.event.head_commit.message`, `github.event.pull_request.title`) sanitized via environment variables
- `qsnyder/action-wxt` replaced with curl command to Webex API
- Curl failure logs warning but doesn't fail workflow (`|| echo "::warning::..."`)
- `workflow_call:` trigger added to test.yml
- notification job condition excludes `workflow_call`
- release.yml `build` job depends on new `test` job via `needs:`

### Must NOT Have (Guardrails)
- ❌ Do NOT modify lint job permissions (already has `contents: write` for valid dependabot reason)
- ❌ Do NOT add retry logic or complex error handling to curl
- ❌ Do NOT create new files or scripts (changes only to existing workflow files)
- ❌ Do NOT modify Python versions, test matrix, or timeouts
- ❌ Do NOT touch dependabot.yml
- ❌ Do NOT add CODEOWNERS, branch protection, or other security features not in audit
- ❌ Do NOT refactor workflow structure (keep jobs as-is, only modify specific lines)
- ❌ Do NOT over-engineer the Webex notification (simple curl, no retry logic)

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: N/A (YAML workflow changes, not Python code)
- **Automated tests**: None (workflow files don't have unit tests)
- **Framework**: N/A

### QA Policy
Every task includes agent-executed QA scenarios using Bash commands to verify:
- YAML syntax validity
- Presence of required patterns (SHAs, permissions, curl)
- Absence of forbidden patterns (qsnyder, `@vX` without SHA)

Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.txt`.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — independent changes):
├── Task 1: Pin all actions to SHAs in both files [quick]
├── Task 2: Add permissions blocks to all jobs [quick]
└── Task 3: Replace qsnyder/action-wxt with curl + sanitization [quick]

Wave 2 (After Wave 1 — integration):
└── Task 4: Add workflow_call trigger and release gating [quick]

Critical Path: Task 1 → Task 4 (Task 4 depends on Task 1 for SHA format consistency)
Parallel Speedup: ~40% faster than sequential
Max Concurrent: 3 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|------------|--------|------|
| 1    | —          | 4      | 1    |
| 2    | —          | —      | 1    |
| 3    | —          | —      | 1    |
| 4    | 1          | —      | 2    |

### Agent Dispatch Summary

- **Wave 1**: **3** — T1 → `quick`, T2 → `quick`, T3 → `quick`
- **Wave 2**: **1** — T4 → `quick`

---

## TODOs

- [ ] 1. Pin All Actions to Commit SHAs (Finding #5)

  **What to do**:
  - Replace all `@vX` or `@vX.Y.Z` action references with `@SHA  # vX.Y.Z` format
  - Use these verified SHAs:
    - `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6`
    - `astral-sh/setup-uv@e06108dd0aef18192324c70427afc47652e63a82  # v7.5.0`
    - `pre-commit/action@2c7b3805fd2a0fd8c1884dcaebf91fc102a13ecd  # v3.0.1`
    - `actions/upload-artifact@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f  # v7`
  - Apply to both `test.yml` (6 action uses) and `release.yml` (2 action uses)

  **Must NOT do**:
  - Do NOT change which actions are used (keep checkout, setup-uv, etc.)
  - Do NOT modify action inputs or configurations
  - Do NOT use different versions than specified above

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple find-and-replace task with clear patterns, low complexity
  - **Skills**: `[]`
    - No special skills needed — standard file editing

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Task 4
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `.github/workflows/test.yml:16` — `actions/checkout@v6` (first occurrence)
  - `.github/workflows/test.yml:44` — `actions/checkout@v6` (second occurrence in lint)
  - `.github/workflows/test.yml:90` — `actions/checkout@v6` (third occurrence in test)
  - `.github/workflows/release.yml:12` — `actions/checkout@v6`
  - `.github/workflows/test.yml:19` — `astral-sh/setup-uv@v7` (first occurrence)
  - `.github/workflows/test.yml:51` — `astral-sh/setup-uv@v7` (second occurrence in lint)
  - `.github/workflows/test.yml:93` — `astral-sh/setup-uv@v7` (third occurrence in test)
  - `.github/workflows/release.yml:15` — `astral-sh/setup-uv@v7`
  - `.github/workflows/test.yml:75` — `pre-commit/action@v3.0.1`
  - `.github/workflows/test.yml:30` — `actions/upload-artifact@v7`

  **External References**:
  - GitHub Dependabot SHA comment format: The `# vX.Y.Z` comment allows Dependabot to track and update SHA pins

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All actions use SHA format
    Tool: Bash
    Preconditions: Files modified with SHA pins
    Steps:
      1. Run: grep -E 'uses:.*@[a-f0-9]{40}' .github/workflows/test.yml | wc -l
      2. Assert output >= 6
      3. Run: grep -E 'uses:.*@[a-f0-9]{40}' .github/workflows/release.yml | wc -l
      4. Assert output >= 2
    Expected Result: test.yml has ≥6 SHA-pinned actions, release.yml has ≥2
    Failure Indicators: Count less than expected, or grep returns no matches
    Evidence: .sisyphus/evidence/task-1-sha-pins.txt

  Scenario: No unpinned version tags remain
    Tool: Bash
    Preconditions: Files modified with SHA pins
    Steps:
      1. Run: grep -E 'uses:.*@v[0-9]' .github/workflows/test.yml | grep -v '@[a-f0-9]' || echo "NONE"
      2. Assert output is "NONE"
      3. Run: grep -E 'uses:.*@v[0-9]' .github/workflows/release.yml | grep -v '@[a-f0-9]' || echo "NONE"
      4. Assert output is "NONE"
    Expected Result: No `@vX` patterns without accompanying SHA
    Failure Indicators: Any line containing `@v` without a SHA
    Evidence: .sisyphus/evidence/task-1-no-unpinned.txt

  Scenario: YAML syntax valid after changes
    Tool: Bash
    Preconditions: Files modified
    Steps:
      1. Run: python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml')); print('VALID')"
      2. Assert output is "VALID"
      3. Run: python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml')); print('VALID')"
      4. Assert output is "VALID"
    Expected Result: Both files parse as valid YAML
    Failure Indicators: Python exception or non-VALID output
    Evidence: .sisyphus/evidence/task-1-yaml-valid.txt
  ```

  **Commit**: YES
  - Message: `security(actions): pin all actions to commit SHAs`
  - Files: `.github/workflows/test.yml`, `.github/workflows/release.yml`
  - Pre-commit: `python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml')); yaml.safe_load(open('.github/workflows/release.yml'))"`

---

- [ ] 2. Add Permissions Blocks (Findings #3, #4)

  **What to do**:
  - Add `permissions: contents: read` to the `security` job in test.yml (after line 12, before `steps:`)
  - Add `permissions: contents: read` to the `test` job in test.yml (after line 80, before `strategy:`)
  - Add `permissions: {}` to the `notification` job in test.yml (after line 110, before `steps:`) — empty permissions since it only needs network access for curl
  - Add `permissions: contents: read` to the `build` job in release.yml (after line 10, before `steps:`)
  - Do NOT modify the `lint` job — it already has `permissions: contents: write` (needed for dependabot lock updates)

  **Must NOT do**:
  - Do NOT change lint job permissions
  - Do NOT add permissions beyond `contents: read` or `{}`
  - Do NOT add workflow-level permissions (keep job-level only)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Adding YAML blocks at specific locations, straightforward
  - **Skills**: `[]`
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: None
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `.github/workflows/test.yml:40-41` — lint job permissions example: `permissions:\n      contents: write`
  - `.github/workflows/test.yml:10-13` — security job structure (add permissions after line 12)
  - `.github/workflows/test.yml:77-80` — test job structure (add permissions after line 80)
  - `.github/workflows/test.yml:105-110` — notification job structure (add permissions after line 110)
  - `.github/workflows/release.yml:9-11` — build job structure (add permissions after line 10)

  **External References**:
  - GitHub docs on job permissions: `permissions: {}` means no permissions (most restrictive)
  - Principle of least privilege: Jobs should only have permissions they need

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Permissions blocks present in test.yml
    Tool: Bash
    Preconditions: Files modified with permissions
    Steps:
      1. Run: grep -A1 'security:' .github/workflows/test.yml | grep -c 'permissions:' || echo "0"
      2. Verify job has permissions (may need to check next few lines)
      3. Run: grep -B5 -A5 'name: Tests' .github/workflows/test.yml | grep 'permissions:'
      4. Run: grep -B5 -A5 'name: Notification' .github/workflows/test.yml | grep 'permissions:'
    Expected Result: security, test, and notification jobs all have permissions blocks
    Failure Indicators: Missing permissions block for any of the three jobs
    Evidence: .sisyphus/evidence/task-2-test-yml-permissions.txt

  Scenario: Permissions block present in release.yml
    Tool: Bash
    Preconditions: release.yml modified
    Steps:
      1. Run: grep -A3 'build:' .github/workflows/release.yml | grep 'permissions:'
      2. Run: grep -A4 'build:' .github/workflows/release.yml | grep 'contents: read'
    Expected Result: build job has `permissions: contents: read`
    Failure Indicators: No permissions block or wrong permission level
    Evidence: .sisyphus/evidence/task-2-release-yml-permissions.txt

  Scenario: lint job permissions unchanged
    Tool: Bash
    Preconditions: Files modified
    Steps:
      1. Run: grep -A2 'lint:' .github/workflows/test.yml | grep -A1 'permissions:' | grep 'contents: write'
    Expected Result: lint job still has `contents: write`
    Failure Indicators: lint job permissions changed from `write` to `read`
    Evidence: .sisyphus/evidence/task-2-lint-unchanged.txt

  Scenario: YAML syntax valid after changes
    Tool: Bash
    Preconditions: Files modified
    Steps:
      1. Run: python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml')); print('VALID')"
      2. Run: python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml')); print('VALID')"
    Expected Result: Both files parse as valid YAML
    Failure Indicators: Python YAML parse exception
    Evidence: .sisyphus/evidence/task-2-yaml-valid.txt
  ```

  **Commit**: YES
  - Message: `security(actions): add least-privilege permissions blocks`
  - Files: `.github/workflows/test.yml`, `.github/workflows/release.yml`
  - Pre-commit: `python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml')); yaml.safe_load(open('.github/workflows/release.yml'))"`

---

- [ ] 3. Replace qsnyder/action-wxt with Curl (Findings #1, #2)

  **What to do**:
  - Remove the `Webex Notification` step that uses `qsnyder/action-wxt@master` (lines 123-133)
  - Add a sanitization step BEFORE the notification that writes user-controlled values to GITHUB_ENV:
    ```yaml
    - name: Sanitize notification variables
      run: |
        # Safely escape commit message for JSON (handles newlines, quotes, special chars)
        COMMIT_MSG=$(echo '${{ github.event.head_commit.message }}' | head -c 500 | jq -Rs .)
        PR_TITLE=$(echo '${{ github.event.pull_request.title }}' | head -c 200 | jq -Rs .)
        echo "SAFE_COMMIT_MSG=${COMMIT_MSG}" >> $GITHUB_ENV
        echo "SAFE_PR_TITLE=${PR_TITLE}" >> $GITHUB_ENV
    ```
  - Add curl-based notification step WITH explanatory comment:
    ```yaml
    # Using direct curl to Webex API instead of a GitHub Action because:
    # - qsnyder/action-wxt is unmaintained (last commit 2022, no releases)
    # - Direct API call has no third-party action dependency to maintain
    # - Gives full control over error handling and message format
    - name: Webex Notification
      if: always()
      run: |
        curl --silent --max-time 30 \
          --request POST \
          --url https://webexapis.com/v1/messages \
          --header "Authorization: Bearer ${{ secrets.WEBEX_TOKEN }}" \
          --header "Content-Type: application/json" \
          --data '{
            "roomId": "${{ secrets.WEBEX_ROOM_ID }}",
            "markdown": "[**[${{ env.jobSuccess }}] ${{ github.repository }} #${{ github.run_number }}**](https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }})\n* Commit: [${{ env.SAFE_COMMIT_MSG }}](${{ github.event.head_commit.url }})${{ env.SAFE_PR_TITLE }}\n* Author: ${{ github.event.sender.login }}\n* Branch: ${{ github.ref }} ${{ github.head_ref }}\n* Event: ${{ github.event_name }}"
          }' \
          || echo "::warning::Webex notification failed"
    ```
  - Preserve the existing message format as closely as possible
  - Use `|| echo "::warning::..."` for error handling (log warning, don't fail workflow)

  **Must NOT do**:
  - Do NOT add retry logic
  - Do NOT create a separate script file
  - Do NOT change the notification job structure (keep same triggers, conditions)
  - Do NOT modify secrets names (keep WEBEX_TOKEN, WEBEX_ROOM_ID)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Replacing one step with two steps, clear requirements
  - **Skills**: `[]`
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: None
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `.github/workflows/test.yml:123-133` — Current qsnyder/action-wxt step to replace
  - `.github/workflows/test.yml:112-121` — Check Job Success step showing GITHUB_ENV pattern

  **External References**:
  - Webex API messages endpoint: `https://developer.webex.com/docs/api/v1/messages/create-a-message`
  - GitHub Actions `::warning::` annotation: Logs warning in Actions UI without failing job

  **WHY Each Reference Matters**:
  - Lines 123-133 show exact current MESSAGE format to preserve
  - Lines 112-121 show how GITHUB_ENV is already used in this workflow

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: qsnyder/action-wxt completely removed
    Tool: Bash
    Preconditions: test.yml modified
    Steps:
      1. Run: grep -c 'qsnyder' .github/workflows/test.yml
    Expected Result: Output is "0"
    Failure Indicators: Any number > 0
    Evidence: .sisyphus/evidence/task-3-qsnyder-removed.txt

  Scenario: curl command present
    Tool: Bash
    Preconditions: test.yml modified
    Steps:
      1. Run: grep 'webexapis.com/v1/messages' .github/workflows/test.yml
    Expected Result: Line containing Webex API URL found
    Failure Indicators: No match found
    Evidence: .sisyphus/evidence/task-3-curl-present.txt

  Scenario: Sanitization step present
    Tool: Bash
    Preconditions: test.yml modified
    Steps:
      1. Run: grep 'SAFE_COMMIT_MSG' .github/workflows/test.yml
      2. Run: grep 'jq -Rs' .github/workflows/test.yml
    Expected Result: Both patterns found (env var and jq escaping)
    Failure Indicators: Missing sanitization
    Evidence: .sisyphus/evidence/task-3-sanitization.txt

  Scenario: Warning handler present
    Tool: Bash
    Preconditions: test.yml modified
    Steps:
      1. Run: grep '::warning::' .github/workflows/test.yml
    Expected Result: Warning annotation pattern found
    Failure Indicators: No error handling for curl failure
    Evidence: .sisyphus/evidence/task-3-error-handling.txt

  Scenario: Explanatory comment present
    Tool: Bash
    Preconditions: test.yml modified
    Steps:
      1. Run: grep -c 'Using direct curl to Webex API' .github/workflows/test.yml
    Expected Result: Output is "1" (comment present)
    Failure Indicators: Comment not found
    Evidence: .sisyphus/evidence/task-3-comment-present.txt

  Scenario: YAML syntax valid after changes
    Tool: Bash
    Preconditions: test.yml modified
    Steps:
      1. Run: python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml')); print('VALID')"
    Expected Result: "VALID"
    Failure Indicators: YAML parse error
    Evidence: .sisyphus/evidence/task-3-yaml-valid.txt
  ```

  **Commit**: YES
  - Message: `security(actions): replace qsnyder/action-wxt with curl`
  - Files: `.github/workflows/test.yml`
  - Pre-commit: `python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"`

---

- [ ] 4. Add workflow_call Trigger and Release Gating (Finding #6)

  **What to do**:
  - In test.yml, add `workflow_call:` to the `on:` triggers (after line 7):
    ```yaml
    on:
      workflow_dispatch:
      pull_request:
      push:
        branches:
          - main
      workflow_call:
    ```
  - Update the notification job condition to exclude workflow_call:
    ```yaml
    if: always() && github.event_name != 'pull_request' && github.event_name != 'workflow_call'
    ```
  - In release.yml, add a `test` job that calls test.yml BEFORE the build job:
    ```yaml
    jobs:
      test:
        uses: ./.github/workflows/test.yml

      build:
        needs: test
        runs-on: ubuntu-latest
        permissions:
          contents: read
        steps:
          ...
    ```

  **Must NOT do**:
  - Do NOT remove existing triggers (keep workflow_dispatch, pull_request, push)
  - Do NOT change test matrix or other test job settings
  - Do NOT add secrets: inherit (test.yml doesn't need secrets when called from release.yml)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Adding trigger and cross-workflow call, clear structure
  - **Skills**: `[]`
    - No special skills needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after Wave 1)
  - **Blocks**: None
  - **Blocked By**: Task 1 (for SHA format consistency in release.yml)

  **References**:

  **Pattern References**:
  - `.github/workflows/test.yml:2-7` — Current `on:` triggers to extend
  - `.github/workflows/test.yml:107` — Current notification job `if:` condition to update
  - `.github/workflows/release.yml:8-22` — Current release structure to modify

  **External References**:
  - GitHub reusable workflows: `uses: ./.github/workflows/test.yml` calls local workflow
  - `needs:` dependency ensures test completes before build starts

  **WHY Each Reference Matters**:
  - Lines 2-7 show where to add workflow_call trigger
  - Line 107 shows current condition that needs workflow_call exclusion
  - Lines 8-22 show release.yml structure where test job must be inserted before build

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: workflow_call trigger present in test.yml
    Tool: Bash
    Preconditions: test.yml modified
    Steps:
      1. Run: grep 'workflow_call' .github/workflows/test.yml
    Expected Result: Match found
    Failure Indicators: No match
    Evidence: .sisyphus/evidence/task-4-workflow-call-trigger.txt

  Scenario: notification job excludes workflow_call
    Tool: Bash
    Preconditions: test.yml modified
    Steps:
      1. Run: grep -A2 'notification:' .github/workflows/test.yml | grep 'workflow_call'
    Expected Result: Condition includes workflow_call exclusion
    Failure Indicators: workflow_call not in notification if condition
    Evidence: .sisyphus/evidence/task-4-notification-condition.txt

  Scenario: release.yml calls test.yml
    Tool: Bash
    Preconditions: release.yml modified
    Steps:
      1. Run: grep 'uses:.*test.yml' .github/workflows/release.yml
    Expected Result: Match found showing test.yml is called
    Failure Indicators: No workflow call to test.yml
    Evidence: .sisyphus/evidence/task-4-release-calls-test.txt

  Scenario: build job depends on test
    Tool: Bash
    Preconditions: release.yml modified
    Steps:
      1. Run: grep -A3 'build:' .github/workflows/release.yml | grep 'needs:.*test'
    Expected Result: `needs: test` found
    Failure Indicators: build job has no needs dependency
    Evidence: .sisyphus/evidence/task-4-build-needs-test.txt

  Scenario: Both YAML files valid
    Tool: Bash
    Preconditions: Both files modified
    Steps:
      1. Run: python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml')); yaml.safe_load(open('.github/workflows/release.yml')); print('VALID')"
    Expected Result: "VALID"
    Failure Indicators: YAML parse error
    Evidence: .sisyphus/evidence/task-4-yaml-valid.txt
  ```

  **Commit**: YES
  - Message: `feat(ci): gate releases on passing tests`
  - Files: `.github/workflows/test.yml`, `.github/workflows/release.yml`
  - Pre-commit: `python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml')); yaml.safe_load(open('.github/workflows/release.yml'))"`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 2 review checks run after implementation. ALL must pass.

- [ ] F1. **YAML Syntax Validation**
  Run `python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"` and same for release.yml. Both must succeed without exceptions.
  Output: `test.yml [VALID/INVALID] | release.yml [VALID/INVALID] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Security Audit Compliance Check**
  Verify all 6 findings addressed:
  1. `grep -c 'qsnyder' .github/workflows/test.yml` = 0
  2. `grep -cE '@[a-f0-9]{40}' .github/workflows/test.yml` ≥ 6
  3. `grep 'permissions:' .github/workflows/test.yml` shows security, test, notification jobs
  4. `grep 'permissions:' .github/workflows/release.yml` shows build job
  5. `grep 'GITHUB_ENV' .github/workflows/test.yml` shows sanitization
  6. `grep 'workflow_call' .github/workflows/test.yml` shows trigger
  Output: `Finding #1 [PASS/FAIL] | #2 [PASS/FAIL] | ... | VERDICT: APPROVE/REJECT`

---

## Commit Strategy

| # | Type | Message | Files | Pre-commit |
|---|------|---------|-------|------------|
| 1 | security | `security(actions): pin all actions to commit SHAs` | test.yml, release.yml | YAML validation |
| 2 | security | `security(actions): add least-privilege permissions blocks` | test.yml, release.yml | YAML validation |
| 3 | security | `security(actions): replace qsnyder/action-wxt with curl` | test.yml | YAML validation |
| 4 | feat | `feat(ci): gate releases on passing tests` | test.yml, release.yml | YAML validation |

---

## Success Criteria

### Verification Commands
```bash
# All actions SHA-pinned
grep -cE '@[a-f0-9]{40}' .github/workflows/test.yml  # Expected: ≥6
grep -cE '@[a-f0-9]{40}' .github/workflows/release.yml  # Expected: ≥2

# qsnyder removed
grep -c 'qsnyder' .github/workflows/test.yml  # Expected: 0

# Permissions present
grep -c 'permissions:' .github/workflows/test.yml  # Expected: ≥3
grep -c 'permissions:' .github/workflows/release.yml  # Expected: ≥1

# workflow_call trigger
grep 'workflow_call' .github/workflows/test.yml  # Expected: match

# Release gating
grep 'needs:.*test' .github/workflows/release.yml  # Expected: match

# YAML valid
python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"  # Expected: no error
python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"  # Expected: no error
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All verification commands pass
