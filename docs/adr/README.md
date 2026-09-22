# Architecture Decision Records

| ADR | Решение | Статус |
|---|---|---|
| [0001](0001-monorepo.md) | Монорепозиторий с разделёнными зонами доверия | accepted |
| [0002](0002-languages.md) | Go + Python + Rego | accepted |
| [0003](0003-nats-outbox.md) | NATS JetStream + transactional outbox | accepted |
| [0004](0004-opa-enforcement.md) | OPA fail-closed в четырёх точках | accepted |
| [0005](0005-supply-chain.md) | SBOM, Cosign keyless, provenance | accepted |
| [0006](0006-strictness-profiles.md) | Профили строгости | accepted |
| [0007](0007-trust-tiers.md) | Trust-tier модель и compression layer | accepted |
| [0008](0008-github-control-plane.md) | GitHub как control plane MVP | accepted |
| [0009](0009-keycloak-oidc.md) | Keycloak / OIDC и scoped service identities | accepted |
| [0010](0010-observability.md) | Observability stack и redaction | accepted |

Новые решения добавляются файлом `NNNN-slug.md` и ADR + `/grill-security` + независимое approval.
