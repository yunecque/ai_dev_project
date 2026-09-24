# Последовательности (sequence diagrams)

Наглядные схемы того, как устроена платформа и как ведётся работа. **Обновляется по мере
прогресса** — при изменении потока правь соответствующую диаграмму и раздел «Прогресс».

Статус milestone: **M0 ✅ · M1 ✅ · M2 ✅ · M3 ✅ · M4 ✅ · M5 ✅ · M6 ✅**

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
транзакцией (transactional outbox). Operator workflow (list/get/update) — REST в gateway (TASK-0002).

```mermaid
sequenceDiagram
    autonumber
    participant Op as Operator
    participant G as gateway (Go)
    participant D as domain (Go)
    participant P as Postgres
    participant Pub as publisher (Go)
    participant N as NATS JetStream

    Op->>G: PATCH /requests/{id}/status (Bearer JWT)
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

Оператор также читает заявки: `GET /requests` (фильтры `status`/`subject`/`limit`) и
`GET /requests/{id}` → gRPC `ListRequests` / `GetRequest`. Авторизация (SPEC-0001/TM-0001):
gateway извлекает роль из OIDC-claim (`operator`/`user`) и передаёт verified context; domain
ограничивает не-operator только своими заявками (чужой id → 404), менять статус может только
operator (иначе 403/PermissionDenied).

Реализация: `apps/domain/internal/domain/{service,memory,postgres}.go` (`CanTransition`, `ListFilter`),
`apps/gateway/server.go` (REST → gRPC, маппинг кодов), `apps/publisher/internal/outbox/poller.go`
(маршрутизация `eventSubjects`), событие — `contracts/events/request-status-changed.schema.json`.
Тесты: `apps/domain/internal/domain/{lifecycle,query}_test.go`, `apps/gateway/server_test.go`,
`poller_test.go`, `test_contracts.py`. Полный operator-flow e2e (create → 4 перехода → read-back,
outbox: 1 created + 4 status-changed) — `postgres_integration_test.go`; async-часть —
`worker/.../e2e_smoke_integration_test.go`.

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

Реализация: `policies/{pre_tool_call,artifact_transition,pre_deployment}.rego`,
`control-plane/src/sdlc/{policy,runner,evidence,trust,waiver}`.
Тесты: `control-plane/tests/test_{policy,runner,evidence,negative_pipeline,waiver,artifact_transition,pre_deployment,deploy_verify}.py`,
`policies/tests/` (opa test). Из четырёх точек ADR-0004 реализованы `pre-tool-call`,
`artifact-transition`, `pre-deployment`; `pr-ci` — остаётся.

---

## 4. Независимый release gate (M3)

Релиз-кандидат проверяется отдельно от build job: evidence собирается в контент-адресуемый
bundle, решение принимает `pre-deployment` policy (fail-closed), результат фиксируется как
`policy-decision`. Agent-approval не считается; нужен human `release-approver`.

```mermaid
sequenceDiagram
    autonumber
    participant CI as CI (deploy-verify)
    participant DV as sdlc deploy-verify
    participant O as OPA (pre_deployment)
    participant Art as evidence bundle + policy-decision

    CI->>DV: release-candidate.json (image, signature, sbom, provenance, decisions, approvals)
    DV->>DV: schema-validate (untrusted) → canonical SHA-256
    DV->>DV: build evidence-bundle (kind/ref/digest, bundle_digest)
    DV->>O: POST /v1/data/sdlc/pre_deployment/decision
    alt allow (signature + sbom + provenance + decisions + human approval)
        O-->>DV: {allow: true}
        DV->>Art: write bundle + decision (allow)
        DV-->>CI: exit 0
    else deny / OPA недоступен (fail-closed)
        O-->>DV: {allow: false, reason_codes}
        DV->>Art: write bundle + decision (deny)
        DV-->>CI: exit 1 (release blocked)
    end
```

Реализация: `control-plane/src/sdlc/deploy_verify/` (`candidate`, `bundle`, `verify`),
`policies/pre_deployment.rego`, CLI `sdlc deploy-verify`. CI: стадия `policy-check` прогоняет
self-test на реальной политике. Контракты: `contracts/schemas/{release-candidate,evidence-bundle}.schema.json`.

---

## 5. Разработка и CI (как агент меняет репозиторий)

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

## 6. Observability pipeline (M4)

Сервисы инструментированы OpenTelemetry (traces/metrics/logs) и экспортируют OTLP в Collector,
который **обязательно** redacts secrets/tokens/PII перед выгрузкой (ADR-0010). Метрики идут в
Prometheus (метка `service_name`), трейсы — в Tempo, логи — в Loki; SLO golden path под алертами.

```mermaid
sequenceDiagram
    autonumber
    participant G as gateway (Go, otelhttp/otelgrpc)
    participant D as domain (Go, otelgrpc)
    participant C as OTel Collector
    participant P as Prometheus
    participant T as Tempo
    participant L as Loki

    G->>D: gRPC (traceparent injected, тот же trace)
    D-->>G: response
    G->>C: OTLP spans/metrics/logs
    D->>C: OTLP spans/metrics/logs
    C->>C: transform/redact: authorization/cookie → [REDACTED];<br/>password|secret|token|api_key → [REDACTED];<br/>email → [REDACTED_EMAIL]
    C->>T: traces
    C->>P: metrics (resource attrs → service_name)
    C->>L: logs
    P->>P: alert rules (GoldenPath{ServiceDown,HighErrorRate,HighLatency})
```

Реализация: `apps/internal/telemetry` (`Setup`, `HTTPHandler`, `GRPCServerOption`),
`infra/compose/otel-collector.yaml` (redaction), `prometheus.yml` + `prometheus/rules/golden-path.yml`,
`grafana/provisioning/{datasources,dashboards}`. Staging — `infra/staging/`.
Guard/тесты: `control-plane/tests/test_{redaction,observability,alerts,staging}.py`,
`apps/internal/telemetry/telemetry_test.go` (в т.ч. `TestGoldenPathObservabilitySmoke`).

---

## 7. Agent execution layer (M6)

Платформа не только проверяет, но и **исполняет** конвейер (ADR-0014). Внешний агент `opencode`
физически ограничен `.opencode/` (нет прямого shell/ФС/сети) и работает только через MCP-мост;
каждый вызов проходит OPA `pre-tool-call` + scoped capability, каждый шаг порождает
`policy-decision`/`evidence-record`.

```mermaid
flowchart LR
    OC[opencode<br/>.opencode profiles] -->|JSON-RPC tools/call| MCP[MCPServer]
    MCP -->|capability auth| EX[RunnerExecutor]
    EX -->|pre-tool-call| OPA[(OPA)]
    EX -->|capability check| CAP[RunRegistry]
    EX -->|allowlisted tool| TOOLS[ToolRegistry<br/>read/write/list_artifact]
    EX --> EV[policy-decision + evidence-record]
    PIPE[Pipeline orchestrator] -->|skill runner| SK[role skills<br/>prompt + contract]
    SK --> LLM[LLM adapter<br/>StubLLM]
    LLM -->|untrusted JSON| VAL[JSON Schema validation]
    VAL --> ART[ArtifactStore]
    PIPE --> EX
    PIPE --> TR[trace_feature = COMPLETE]
    PLUG[.opencode plugin opa-guard] -->|tool.execute.before / permission.ask| OPA
```

Роли: `grill`→specification, `grill-security`→threat-model, `planner`→plan, `task-writer`→task,
`reviewer`→review; `security-review` компилируется платформой детерминированно из threat-model.
Sensitive не попадает в model context; LLM-output — untrusted data, инъекции полей игнорируются.

Реализация: `control-plane/src/sdlc/{tools,runner/executor,llm,skills,mcp,pipeline}`,
`.opencode/` (`opencode.json`, `plugin/opa-guard.ts`, `agent/*.md`). Guard/тесты:
`control-plane/tests/test_{tools,executor,skills,mcp,pipeline,opencode_config}.py`.

---

## 8. Прогресс по milestone

| Milestone | Статус | Диаграмма |
|---|---|---|
| M0 Фундамент | ✅ | — |
| M1 Walking skeleton | ✅ | §1, §3, §5 |
| M2 Домен и lifecycle | ✅ | §2 |
| M3 Supply chain hardening | ✅ | §3 (pre-deployment), §4 |
| M4 Staging + observability | ✅ | §6 |
| M5 Portfolio | ✅ | `docs/security-demos.md`, `sdlc trace` |
| M6 Agent execution layer | ✅ | §7 |

### Как обновлять
1. Меняя поток — правь соответствующую Mermaid-диаграмму.
2. Меняя статус этапа — обновляй строку в таблице и строку «Статус milestone» сверху.
3. Держи `PROGRESS.md` и `README.md` согласованными с этим файлом.