# Roadmap

## MVP (in scope)

Контур `Idea → /grill → spec → /grill-security (STRIDE) → plan → tasks → TDD → review
→ CI gates → SBOM + provenance + signature → staging → monitoring`.

- **M0 — Фундамент:** окружение, монорепо, baseline, ADR, JSON Schemas, локальный compose,
  CI-каркас, GitHub control plane.
- **M1 — Walking skeleton:** одна vertical slice `RequestCreated` сквозь весь контур.
- **M2 — Домен и lifecycle:** operator workflow, полная authz-матрица, waiver-механика.
- **M3 — Supply chain hardening:** Cosign keyless, attestations, независимый `deploy-verify`.
- **M4 — Staging + observability:** mini PC staging, OTel, dashboards, alerts, redaction.
- **M5 — Portfolio:** traceability chain, 4 демонстрации заблокированных атак, ограничения.

## Отложено (explicit backlog)

| Пункт | Причина отсрочки | Условие перехода |
|---|---|---|
| Production deployment | MVP — staging-only | стабильный staging + второй reviewer + prod-grade secrets |
| Второй независимый human reviewer | solo-mode MVP | появление второго участника |
| Kubernetes | сложность для demo-масштаба | необходимость multi-node / autoscaling |
| Дополнительные бизнес-домены | фокус на одном golden path | закрытие M2–M4 |
| Дополнительные языки | контракт покрыт Go/Python/Rego | доказанная необходимость через ADR |
| CDC-based outbox (Debezium) | outbox-таблица достаточна | нагрузка/требования к лагу |
| Автономный incident triage | риск без human-in-the-loop | зрелость policy + evidence |
| Собственный web UI control plane | GitHub покрывает MVP | ограничения GitHub как control plane |
| Provenance без GitHub | vendor lock-in | требование независимого CI |

## Правило изменений

Изменения roadmap — только через ADR. Перенос пункта из backlog в MVP требует обновления
этого файла и соответствующего ADR.
