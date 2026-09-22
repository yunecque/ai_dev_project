# Secure Agentic SDLC

Policy-driven платформа агентной разработки, которая преобразует идею в проверяемый релиз
через спецификации, изолированное выполнение, обязательные security gates и подтверждённую
цепочку поставки.

LLM рассматривается как **недоверенный компонент**: он не получает постоянные production-секреты,
не выполняет произвольные команды без policy-проверки, не утверждает собственный код и не может
отключить обязательные проверки.

## Целевой контур MVP

```
Idea → /grill → approved specification → /grill-security (STRIDE) threat model
→ implementation plan → tasks → TDD implementation in ephemeral sandbox
→ independent review → CI security gates → SBOM + provenance + signature
→ staging deployment → monitoring
```

Первая golden-path feature: аутентифицированный пользователь создаёт заявку через REST;
gateway передаёт verified identity context по gRPC в domain service; сервис сохраняет заявку и
событие `RequestCreated` в одной PostgreSQL-транзакции (transactional outbox); publisher
доставляет событие в NATS JetStream; worker обрабатывает его идемпотентно.

## Структура репозитория

| Зона | Назначение | Доверие |
|---|---|---|
| `apps/<service>/` | функциональный код (изменяется агентом через PR) | untrusted |
| `control-plane/` | агентная платформа: runner, skills, policy, evidence | trusted (код), untrusted (LLM output) |
| `specs/` | specifications, threat models, plans, tasks | trusted после approval |
| `contracts/` | OpenAPI, Protobuf, event schemas, JSON Schema | trusted |
| `policies/` | OPA/Rego | trusted (CODEOWNERS) |
| `security/` | threat-model templates, security tests | trusted (CODEOWNERS) |
| `infra/` | staging infra, deployment manifests | trusted (CODEOWNERS) |
| `.github/workflows/` | CI/CD | trusted (CODEOWNERS) |
| `docs/` | ADR, roadmap, evidence model | trusted |

## Governance

- Текущее состояние и handoff: [`PROGRESS.md`](PROGRESS.md).
- Профиль строгости: **strict** (см. `baseline.json`, `ARCHITECTURE_BASELINE.md`).
- Архитектурные решения: `docs/adr/`.
- Roadmap и отложенный backlog: `docs/roadmap.md`.
- Модель evidence: `docs/evidence-model.md`.
- Схемы workflow-артефактов: `contracts/schemas/`.
- Git — единственный source of truth. Markdown генерируется из JSON-артефактов.

## Навигация агента

См. `AGENTS.md` для правил работы с репозиторием и обязательных проверок перед PR.
