# Последовательности (sequence diagrams)

Наглядные схемы того, как устроена платформа и как ведётся работа. **Обновляется по мере
прогресса** — при изменении потока правь соответствующую диаграмму и раздел «Прогресс».

Статус milestone: **M0 ✅ · M1 ✅ · M2 ⏳ · M3 · M4 · M5**

Источники: `README.md` (модель исполнения/контроля), `docs/adr/`, `PROGRESS.md`.

---

## 1. Golden path (runtime)

Аутентифицированный пользователь создаёт заявку; событие доставляется воркеру.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant G as gateway (Go)
    participant K as Keycloak (OIDC)
    participant D as domain (Go)
    participant P as Postgres
    participant Pub as publisher (Go)
    participant N as NATS JetStream
    participant W as worker (Go)

    C->>G: POST /requests (Authorization: Bearer JWT)
    G->>K: verify token (JWKS)
    K-->>G: subject
    G->>D: gRPC CreateRequest(title, description, subject)
    D->>D: validate (title/subject)
    D->>P: INSERT request + INSERT outbox  (одна транзакция)
    P-->>D: commit
    D-->>G: Request(id, status=created, created_at)
    G-->>C: 201 Created

    loop poll
        Pub->>P: SELECT outbox WHERE published_at IS NULL
        Pub->>N: publish "requests.created"
        Pub->>P: UPDATE published_at
    end

    N-->>W: deliver RequestCreated
    W->>W: dedupe(event_id) → apply (ровно один раз)
```

Реализация: `apps/gateway`, `apps/domain`, `apps/publisher`, `apps/worker`,
контракты — `contracts/{openapi,proto,events}`. Тесты e2e: `apps/worker/.../e2e_smoke_integration_test.go`.

---

## 2. Lifecycle заявки (M2)

State machine `created → triaged → in_progress → resolved → closed` (+ `cancelled` из первых трёх).
Изменить статус можно только по разрешённому переходу; изменение статуса и событие пишутся одной
транзакцией (transactional outbox). REST-часть (`PATCH /requests/{id}/status`) — TASK-0002.

```mermaid
sequenceDiagram
    autonumber
    participant Op as Operator
    participant G as gateway (Go)
    participant D as domain (Go)
    participant P as Postgres
    participant Pub as publisher (Go)
    participant N as NATS JetStream

    Op->>G: PATCH /requests/{id}/status (Bearer JWT)   %% TASK-0002
    G->>D: gRPC UpdateRequestStatus(id, new_status, actor)
    D->>P: SELECT request
    D->>D: CanTransition(current → new)
    alt переход разрешён
        D->>P: UPDATE requests SET status + INSERT outbox (одна транзакция)
        D-->>G: Request(status=new)
        G-->>Op: 200 OK
    else запрещённый переход / нет заявки
        D-->>G: FailedPrecondition / NotFound
        G-->>Op: 409 / 404
    end
    Pub->>P: SELECT outbox WHERE published_at IS NULL
    Pub->>N: publish requests.status-changed (route по типу события)
```

Реализация: `apps/domain/internal/domain/{service,memory,postgres}.go` (`CanTransition`),
`apps/publisher/internal/outbox/poller.go` (маршрутизация `eventSubjects`), событие —
`contracts/events/request-status-changed.schema.json`.
Тесты: `apps/domain/internal/domain/lifecycle_test.go`, `poller_test.go`, `test_contracts.py`.

---

## 3. Enforcement вокруг агента (untrusted)

Каждый tool-call проходит policy (OPA) и scoped capability; sensitive не попадает в контекст.

```mermaid
sequenceDiagram
    autonumber
    participant Ag as Agent (untrusted)
    participant M as Platform (MCP/runner)
    participant O as OPA (Rego)
    participant Cap as Capability token
    participant Ev as Evidence store

    Ag->>M: tool call {tool, path, args}
    M->>O: POST /v1/data/sdlc/pre_tool_call/decision
    alt allow
        O-->>M: {allow: true}
    else deny / OPA недоступен (fail-closed)
        O-->>M: {allow: false, reason_codes: [...]}
        M-->>Ag: blocked
    end

    M->>Cap: check(token, tool, scope)
    alt capability валидна
        Cap-->>M: CAPABILITY_VALID
        M->>Ev: put byte-exact output (+ compression)
        M-->>Ag: bounded context / результат
    else истекла / не тот tool/scope / отозвана
        Cap-->>M: reason
        M-->>Ag: blocked
    end
```

Реализация: `policies/pre_tool_call.rego`, `control-plane/src/sdlc/{policy,runner,evidence,trust}`.
Тесты: `control-plane/tests/test_{policy,runner,evidence,negative_pipeline}.py`.

---

## 4. Разработка и CI (как агент меняет репозиторий)

```mermaid
sequenceDiagram
    autonumber
    participant Dev as Agent / Dev
    participant Br as feature branch
    participant PR as Pull Request
    participant CI as GitHub Actions
    participant Main as main (protected)

    Dev->>Br: task: contract → code → test
    Dev->>PR: gh pr create
    PR->>CI: 15 required checks
    CI-->>PR: schema-validate, lint, typecheck, secret-scan,<br/>unit, contract, sast, dependency-scan,<br/>integration, security, policy-check, build-image
    alt все зелёные
        PR->>Main: squash merge (solo-mode, ADR-0012)
        Main->>Br: delete branch
    else есть падение
        CI-->>Dev: failing check
        Dev->>Br: fix → push
    end
```

---

## 5. Прогресс по milestone

| Milestone | Статус | Диаграмма |
|---|---|---|
| M0 Фундамент | ✅ | — |
| M1 Walking skeleton | ✅ | §1, §3, §4 |
| M2 Домен и lifecycle | ⏳ | §2 |
| M3 Supply chain hardening | — | (container-scan / sbom / sign) |
| M4 Staging + observability | — | (otel pipeline) |
| M5 Portfolio | — | (traceability, blocked attacks) |

### Как обновлять
1. Меняя поток — правь соответствующую Mermaid-диаграмму.
2. Меняя статус этапа — обновляй строку в таблице и строку «Статус milestone» сверху.
3. Держи `PROGRESS.md` и `README.md` согласованными с этим файлом.