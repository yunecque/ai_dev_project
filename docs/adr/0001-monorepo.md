# ADR-0001: Монорепозиторий с разделёнными зонами доверия

- **Статус:** accepted
- **Дата:** 2026-09-21
- **Контекст:** Агент изменяет функциональный код, но не должен иметь возможности менять
  policy, CI и security-контролы. Нужен единый source of truth и атомарные PR, охватывающие
  contract + code + test (вертикальный срез).
- **Решение:** один монорепозиторий с явными зонами: `apps/` (agent-mutable через PR),
  `specs/`, `contracts/`, `policies/`, `security/`, `infra/`, `.github/workflows/`, `docs/`.
  Защищённые зоны контролируются `CODEOWNERS`.
- **Обоснование:** атомарность vertical slice, единая traceability, простое CODEOWNERS/branch
  protection. Полирепо усложнил бы линковку spec↔code↔CI.
- **Последствия:** необходим жёсткий CODEOWNERS и branch protection; рост репозитория
  компенсируется path-scoped CI.
- **Ссылки:** конституция §7; ADR-0008.
