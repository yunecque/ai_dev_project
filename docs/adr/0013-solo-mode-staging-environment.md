# ADR-0013: Solo-mode политика environment-гейта `staging`

- **Статус:** accepted (временно, до появления второго участника)
- **Дата:** 2026-09-24
- **Контекст:** ADR-0005 требует для `deploy-verify` environment `staging` с required reviewer.
  GitHub запрещает self-approval environment protection: единственный collaborator в solo-mode —
  владелец, и он не может утвердить собственный деплой. С required reviewer это даёт deadlock
  (аналог проблемы, решённой для review в ADR-0012). При этом независимая проверка
  signature/SBOM/provenance и OPA `pre-deployment` — ценность, которую нельзя отключать.
- **Решение:** в solo-mode environment `staging` создаётся **без** `required_reviewers`; гейт
  обеспечивается не human-approval environment, а обязательными независимыми проверками:
  - деплой только через `deploy-verify` (`workflow_dispatch`) на protected `main`;
  - независимая проверка `cosign verify` (signature), `cosign verify-attestation` (SBOM),
    `gh attestation verify` (provenance) в отдельных job'ах, не разделяющих состояние со сборкой;
  - OPA `pre-deployment` fail-closed: отсутствие/непроверенность signature/SBOM/provenance,
    отсутствие allow-решений `artifact-transition`+`pr-ci` или отсутствие human-approval — deny;
  - `required_approver_role=release-approver` заполняется из manual actor (`github.actor`) как
    human — только при ручном dispatch; агент не может триггерить/утверждать
    (`AGENT_MAY_NOT_APPROVE`).
  Сохраняются: environment `staging` (deployment branch policy = protected `main`), audit trail,
  обязательность verification. `administrators can bypass` не требуется.
- **Обоснование:** автоматические независимые гейты — самая ценная и наименее подверженная
  влиянию часть контроля; human environment-review в solo-mode создаёт deadlock и не даёт
  независимости. Это конфигурационное отклонение solo-mode, **не** waiver на findings и не
  отмена обязательных security gates.
- **Условие возврата:** при появлении второго участника — включить required reviewer на `staging`
  (роль `release-approver`, 1; один из них security) и, при необходимости, wait timer; вернуть
  review-политику согласно ADR-0012.
- **Последствия:** в solo-mode staging deploy запускается владельцем без независимого
  environment-review. Verification остаётся обязательной и fail-closed, Critical/High findings
  по-прежнему блокируют deployment всегда.
- **Ссылки:** ADR-0005; ADR-0008; ADR-0012; `docs/branch-protection.md`; `docs/roadmap.md`.

## Применение

Environment создаётся из репозитория (после аутентификации `gh`):

```powershell
./infra/github/apply-staging-environment.ps1 -Repo yunecque/ai_dev_project
```

Проверить: Settings → Environments → `staging` → Deployment branches = Protected branches.
