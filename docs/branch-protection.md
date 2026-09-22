# Branch protection и required checks

GitHub — control plane MVP (ADR-0008). Настройки применяются к `main` и к staging environment.

## `main` (protected)

- Require a pull request before merging.
  - Require approvals: **0** в solo-mode (ADR-0012). При появлении второго участника — **1**,
    затем **2** (один из них security).
  - Dismiss stale approvals on new commits: **on**.
  - Require review from Code Owners: **off** в solo-mode (ADR-0012); **on** при появлении второго
    участника.
- Require status checks to pass before merging: **on**.
  - Require branches to be up to date: **on**.
- Require conversation resolution: **on**.
- Require signed commits: **on** (recommended).
- Do not allow bypassing the above settings: **on**.
- Restrict who can push: только через PR.

### Required status checks (порядок §9)

| # | Check | Workflow |
|---|---|---|
| 1 | `schema-validate` | `ci.yml` |
| 2 | `lint` | `ci.yml` |
| 3 | `typecheck` | `ci.yml` |
| 4 | `secret-scan` | `ci.yml` |
| 5 | `unit-tests` | `ci.yml` |
| 6 | `contract-tests` | `ci.yml` |
| 7 | `sast` | `ci.yml` |
| 8 | `dependency-scan` | `ci.yml` |
| 9 | `integration-tests` | `ci.yml` |
| 10 | `security-tests` | `ci.yml` |
| 11 | `policy-check` | `ci.yml` |
| 12 | `build-image` | `ci.yml` |
| 13 | `container-scan` | `ci.yml` |
| 14 | `sbom-generate` | `ci.yml` |
| 15 | `sign-and-attest` | `ci.yml` |

> Стадии 12–15 запускаются только из protected branch на смерженном commit.

## Environment `staging`

- Required reviewers: **release-approver** (solo-mode: владелец, `solo_override=true` с обоснованием
  в audit trail).
- Wait timer: по необходимости.
- Deployment branches: только `main`.
- `deploy-verify` workflow проверяет signature/SBOM/provenance/policy/approvals **независимо**
  от build job.

## Правила, которые нельзя отключить

- Critical/High findings блокируют merge и deployment **всегда**, без исключений.
- Solo override никогда не отменяет Critical/High, signature/SBOM/provenance и required security gates.
- Агент не может создавать, утверждать, продлевать или применять waivers.

## Применение

Пока `gh` не установлен и remote не создан, настройки применяются вручную в Settings → Branches.
После подключения GitHub — скриптом `infra/github/apply-branch-protection.ps1`.
