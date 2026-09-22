# Architecture Baseline v1

- **Baseline ID:** `BASELINE-V1`
- **Версия:** 1.0.0
- **Статус:** approved
- **Профиль строгости:** `strict`
- **Утвердил:** platform-owner
- **Дата:** 2026-09-21
- **Машиночитаемый источник:** [`baseline.json`](../baseline.json) (JSON Schema: `contracts/schemas/baseline.schema.json`)

> Любая новая технология, сервис, привилегия, dependency class или deployment capability
> требует **ADR + `/grill-security` + policy validation + независимое approval**.
> Агенты используют только то, что перечислено ниже.

## 1. Языки

| Роль | Технология | Версия |
|---|---|---|
| Production-сервисы (gRPC, обработка сообщений) | Go | >= 1.22 |
| Agent / control plane, automation | Python | 3.12.x (пин) |
| Policy-as-code | Rego | OPA >= 0.66 |

## 2. Коммуникация

- **Наружу:** REST/JSON + OpenAPI 3.1.
- **Между сервисами:** gRPC + Protobuf.
- **Доменные события:** NATS JetStream, transactional outbox + идемпотентные consumers.

## 3. Identity

- OIDC, Keycloak как identity provider.
- Отдельные scoped service identities: `gateway`, `domain-service`, `broker-publish`,
  `broker-subscribe`, `ci-deployment-workload`.

## 4. Policy engine

- OPA / Rego, fail-closed.
- Четыре обязательные точки: `pre-tool-call`, `artifact-transition`, `pr-ci`, `pre-deployment`.
- Решения — machine-readable allow/deny с reason codes, версией policy bundle, input digest,
  actor/run ID; хранятся как evidence.

## 5. Контейнеризация

- Docker / Docker Compose.

## 6. Observability

- OpenTelemetry (traces/metrics/logs) → OTel Collector.
- Metrics: Prometheus/Grafana; Logs: Loki; Traces: Tempo.
- Обязательная redaction секретов, токенов и PII перед экспортом.

## 7. Security tooling

| Задача | Инструмент |
|---|---|
| Secrets | Gitleaks |
| SAST | Semgrep / CodeQL |
| Dependency + container scan | Trivy |
| SBOM | Syft |
| Signing | Cosign + GitHub OIDC (keyless) |
| Provenance | GitHub artifact attestations |

## 8. Deployment target

- Локально сейчас → mini PC (staging) далее → облако опционально.
- Application/security contracts не меняются при смене target.

## 9. Профили строгости

- **strict** — платформа и security-критичные проекты: полный `/grill-security`, полный review-цикл.
- **personal-project** — внутренние утилиты без внешних пользователей и чувствительных данных:
  облегчённый threat modeling, но supply-chain controls (signing, SBOM, secret scanning)
  обязательны **всегда**.

Текущий профиль — `strict` (задекларирован в `baseline.json`).

## 10. Условия изменения

Baseline меняется только через ADR с независимым approval и `/grill-security` для
security-значимых изменений. Изменения roadmap — только через ADR.
