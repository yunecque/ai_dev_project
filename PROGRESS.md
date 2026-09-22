# PROGRESS

Состояние реализации Secure Agentic SDLC. Самодостаточный handoff: новая сессия/человек
продолжает отсюда, прочитав также `AGENTS.md` и `ARCHITECTURE_BASELINE.md`.

- Обновлено: 2026-09-22
- Текущий milestone: **M1 — Walking skeleton** (завершён)
- Следующий: **M2 — Домен и lifecycle**
- Remote: https://github.com/yunecque/ai_dev_project (main, protected)

---

## 1. Статус по milestone

| Milestone | Статус | Примечание |
|---|---|---|
| M0 Фундамент | 100% | завершён; remote + branch protection применены |
| M1 Walking skeleton | 100% | TASK-0001…0012 done; walking skeleton собран |
| M2 Домен и lifecycle | не начат | |
| M3 Supply chain hardening | не начат | |
| M4 Staging + observability | не начат | |
| M5 Portfolio | не начат | |

### M0 checklist

- [x] Структура монорепо (§7)
- [x] `baseline.json` + `ARCHITECTURE_BASELINE.md` (профиль `strict`)
- [x] ADR 0001–0011 + индекс (0011 — граница контроля и размещение агента)
- [x] `docs/roadmap.md`, `docs/evidence-model.md`, `docs/branch-protection.md`
- [x] JSON Schemas всех workflow-артефактов + примеры в `specs/examples/`
- [x] Control plane: валидатор + рендерер JSON→Markdown (`sdlc validate|render`), тесты
- [x] CODEOWNERS, PR/issue templates, скрипты branch protection
- [x] Локальный стек `infra/compose/` (проверен, все сервисы healthy)
- [x] CI skeleton `.github/workflows/ci.yml` + `deploy-verify.yml`
- [x] Toolchain в WSL (user-local, без sudo), `infra/wsl/toolchain.lock`
- [x] `.gitattributes` (LF-нормализация для кросс-платформенности)
- [x] GitHub repo + push + branch protection → https://github.com/yunecque/ai_dev_project (15 required checks, enforce_admins, 1 review)

---

## 2. Окружение (проверено)

### Windows (host)

| Компонент | Версия / состояние |
|---|---|
| OS | Windows 11 Pro |
| Hypervisor | present |
| WSL2 | установлен; distros: `Ubuntu`, `docker-desktop` (обе Running) |
| Docker Desktop | 4.91.0; `docker` 29.8.0, linux/Docker Desktop |
| Python (system) | 3.14.0 |
| Python 3.12 | 3.12.10 (winget `Python.Python.3.12`) — пин для control-plane |
| git | 2.54.0.windows.1 |

### WSL Ubuntu (user `zarl3`, x86_64)

Toolchain установлен user-local: `~/.local/bin`, `~/.local/go`. Версии — `infra/wsl/toolchain.lock`:

```
go=go1.27.1   opa=v1.20.2   gh=v2.101.0   cosign=v3.1.3
syft=v1.52.0  trivy=v0.74.0 gitleaks=v8.30.1 buf=v1.73.0
semgrep=1.177.0  uv=0.12.17
```

`PATH` прописан в `~/.profile` и `~/.bashrc`. `sudo` требует пароль (системные пакеты не ставились;
не потребовалось — всё user-local).

### Локальный стек (`infra/compose/`)

Запущен, проверен (`docker compose ... ps` — все Up; postgres/nats healthy):

| Endpoint | URL | Проверено |
|---|---|---|
| OPA | http://localhost:8181/health | 200 |
| NATS monitor | http://localhost:8222/healthz | 200 |
| Keycloak (realm `sdlc`) | http://localhost:8080 | 200 |
| Prometheus | http://localhost:9090 | 200 |
| Grafana | http://localhost:3000 | 200 |
| Loki | http://localhost:3100/ready | 200 |
| Tempo | http://localhost:3200/ready | 200 |
| Postgres | localhost:5432 | healthy |

`.env` создан из `.env.example` (gitignored). Dev-креды — только локальные.

---

## 3. Проверки (зелёные)

```bash
# control-plane (Python)
cd control-plane
python -m ruff check src tests      # All checks passed
python -m mypy                      # Success: no issues found (17 files, strict)
python -m pytest -q                 # 70 passed
sdlc validate ../specs/examples/*.json   # все OK
sdlc validate ../baseline.json           # OK

# apps (Go)
cd apps
gofmt -l . && go vet ./...          # clean
go test ./...                       # unit
go test -tags=integration ./...     # integration (Postgres gated by TEST_DATABASE_URL)

# policy (Rego)
opa fmt --fail policies/ && opa test policies/   # 7/7
```

CI: 15 required checks; `build-image` собирает 4 образа, `dependency-scan` (Trivy),
`sast` (Semgrep), `security-tests` (tests + Trivy secrets), `integration-tests` (Postgres service).
Все JSON и YAML в репозитории парсятся; compose config валиден.

---

## 4. Что уже в репозитории

```
apps/{gateway,domain,worker}/     # gateway REST+OIDC+gRPC; domain gRPC+outbox; worker consumer
apps/publisher/                   # outbox poller -> NATS JetStream (Go)
apps/domain/migrations/0001_init.sql  # requests + outbox
apps/worker/migrations/0002_processed_events.sql  # идемпотентность consumer'а
apps/go.mod                       # единый Go-модуль github.com/yunecque/ai_dev_project/apps
apps/gen/domain/v1/               # сгенерированный из proto код (buf, local plugins)
control-plane/                    # Python 3.12: src/sdlc (artifacts, policy, runner, evidence), tests
contracts/schemas/                # 12 JSON Schema (workflow artifacts)
contracts/openapi/requests.yaml   # REST-контракт golden path (OpenAPI 3.1)
contracts/proto/domain/v1/domain.proto  # gRPC-контракт DomainService
contracts/events/                 # request-created.schema.json + examples/
policies/                         # pre_tool_call.rego (Rego v1) + tests/
security/{threat-models,tests}/   # пусто — M1
infra/compose/                    # рабочий стек
infra/wsl/                        # bootstrap-toolchain.sh + README + lock
infra/github/                     # apply-branch-protection.ps1 + setup-remote.sh
specs/examples/                   # 10 валидных примеров golden-path
.github/workflows/                # ci.yml, deploy-verify.yml
docs/{adr,roadmap.md,evidence-model.md,branch-protection.md}
baseline.json, ARCHITECTURE_BASELINE.md, AGENTS.md, README.md
```

### Зафиксированные решения (2026-09-22)

Документированы в `README.md` («Модель исполнения и контроля») и `docs/adr/0011-...`:

- Продукт A (платформа) и B (reference-приложение) разведены.
- Инструкции = in-band, не контроль; enforcement только out-of-band.
- Граница = capability removal + mediation (MCP + OPA pre-tool-call) + tamper-proofing.
- Размещение агента: M1 — host; цель — контейнер; sandbox всегда эфемерный.
- Ограничение opencode через `.opencode/` (MCP + `permission` + plugin→OPA); роли → profiles.
- Solo-mode review: ADR-0012 (0 approvals при сохранении автогейтов).

---

## 5. Открытые пункты / блокеры

1. **M0 закоммичен и запушен.** Commit `2570c2e` на `main` (repo public, branch protection активна).
2. **PR #1 (`chore/m0-progress`) разблокирован.** Политика review решена: **ADR-0012** —
   solo-mode `required_approving_review_count=0` + `require_code_owner_reviews=false`; 15 required
   checks, `enforce_admins`, PR-only и запрет force-push сохранены. Возврат к human review — при
   появлении второго участника.
3. **Создать `staging` environment** в GitHub с required reviewer (`release-approver`) — для M4/release gate.
4. Опционально: `sudo apt install -y python3-venv` (не требуется, semgrep поставлен через `uv`).

---

## 6. Как продолжить (M1)

Порядок M1 (walking skeleton), feature `FEAT-0001`:

- [x] **TASK-0001** — control-plane `policy`: OPA `pre-tool-call` клиент, fail-closed,
  `policy-decision` artifact + тесты (`src/sdlc/policy/`, `tests/test_policy.py`).
- [x] **TASK-0002** — `contracts/`: OpenAPI (`requests.yaml`), Protobuf (`domain/v1/domain.proto`),
  event schema (`request-created.schema.json`) + `tests/test_contracts.py` (6 тестов).
- [x] **TASK-0003** — control-plane `runner`: ephemeral run, scoped capability token, `run_id`.
  - `RunRegistry` (start/finish/issue/check), HMAC-signed `v1.<payload>.<sig>` capabilities,
    fail-closed (malformed/tampered/expired/mismatch/unknown/revoked), `tests/test_runner.py` (11).
- [ ] **TASK-0004** — control-plane `evidence`: compression layer + recovery handle; `trust` tiers.
  - [x] сделано: `trust.py` (tiers + `classify_source`/`can_use_as_instruction`),
    `evidence/` (EvidenceStore content-addressed, compress_for_context, build_evidence_record,
    process_tool_output с запретом sensitive в контексте), `tests/test_trust.py` + `test_evidence.py` (20).
- [x] **TASK-0005** — `apps/gateway` (Go): REST + OIDC validation + gRPC client.
  - Go-модуль `apps` (module `github.com/yunecque/ai_dev_project/apps`), buf-кодогенерация
    (`contracts/proto/buf*.yaml`, local protoc-gen-go/-grpc) → `apps/gen/domain/v1`.
  - `gateway`: `POST /requests` (Bearer JWT → subject → gRPC `CreateRequest`), `GET /healthz`;
    OIDC verifier (`go-oidc`); fail-closed 401/400/502. Тесты через bufconn + fake verifier (10).
  - CI: Go-шаги переведены на `apps/go.mod` (`go-version-file`, `gofmt`, `go vet`, `go test`).
- [x] **TASK-0006** — `apps/domain` (Go): gRPC + Postgres + transactional outbox.
  - `internal/domain`: `Service` (gRPC `DomainService`), `Store` interface,
    `MemoryStore` (tests/dev), `PostgresStore` (pgx, atomic insert request+outbox),
    `migrations/0001_init.sql`. Тесты: request+event в одной транзакции, валидация,
    сверка outbox payload с контрактом события (9). Go: gofmt/vet/test зелёные.
- [x] **TASK-0007** — outbox publisher → NATS; `apps/worker` идемпотентный consumer.
  - `apps/publisher`: `outbox.Poller` (Fetch→Publish→Mark, стоп на первой ошибке),
    `PostgresStore`, `NATSPublisher` (JetStream), main с bootstrap stream `REQUESTS`.
  - `apps/worker`: `consumer.Handler` (validate→dedupe→apply ровно один раз),
    `MemoryDedupe`/`PostgresDedupe` (`ON CONFLICT DO NOTHING`), JetStream durable `worker`.
  - Тесты на фейках: poller (5) + handler (6). Реальный NATS/Postgres — в TASK-0008.
- [x] **TASK-0008** — интеграционные тесты (build-tag `integration`).
  - `domain` Postgres: атомарная запись request+outbox и rollback при конфликте (gated по
    `TEST_DATABASE_URL`).
  - `publisher`↔NATS и `worker`↔NATS: встроенный JetStream, идемпотентность дубликата.
  - CI: джоба `integration-tests` с сервисом Postgres + `go test -tags=integration ./...`.
  - Осталось (перенесено): authorization/security/negative_pipeline/e2e_smoke — в TASK-0009.
- [x] **TASK-0009** — CI-стадии `policy-check` и `contract-tests`.
  - `policies/pre_tool_call.rego` (Rego v1): allowlist инструментов, запрет sensitive-путей
    (`.env`, `secrets/`, `*.key`, ...), fail-closed deny с reason codes; query path
    `/v1/data/sdlc/pre_tool_call/decision` (совпадает с `PolicyClient`).
  - `policies/tests/pre_tool_call_test.rego`: 7 тестов. CI: `opa fmt --fail` + `opa test`.
  - compose OPA обновлён 0.68.0 → 1.20.2 (Rego v1).
  - `contract-tests`: `buf lint contracts/proto` + `pytest control-plane/tests/test_contracts.py`.
- [x] **TASK-0010** — CI-стадии `sast` и `security-tests`.
  - `security/semgrep/rules.yaml`: локальные правила (shell=True, eval/exec, TLS skip-verify,
    requests verify=False); CI `sast` = `semgrep scan --config ... --error`.
  - CI `security-tests` = control-plane security-тесты (policy/runner/evidence/trust) +
    `trivy fs --scanners secret --exit-code 1`.
- [x] **TASK-0011** — CI-стадии `build-image` и `dependency-scan`.
  - Dockerfile'ы `apps/{gateway,domain,publisher,worker}/Dockerfile` (multi-stage,
    `CGO_ENABLED=0`, distroless `static-debian12:nonroot`), `apps/.dockerignore`.
  - CI `build-image`: сборка всех 4 образов (context `apps/`) на PR и push.
  - CI `dependency-scan`: Trivy vuln по `apps/go.mod` (`--severity HIGH,CRITICAL --ignore-unfixed`).
- [x] **TASK-0012** — тесты authorization / negative_pipeline / e2e_smoke.
  - gateway `authorization_test.go`: только Bearer, пустой токен → 401, тело не может
    переопределить subject, разные токены → разные subject.
  - control-plane `test_negative_pipeline.py`: композиция policy+capability, fail-closed,
    sensitive не попадает в контекст, untrusted/sensitive не инструкции.
  - worker `e2e_smoke_integration_test.go`: golden event из контракта через embedded JetStream
    обрабатывается ровно один раз (смыкает async golden path с domain payload-тестом).

## 7. Полезные команды

```bash
# стек
docker compose -f infra/compose/docker-compose.yml --env-file infra/compose/.env up -d
docker compose -f infra/compose/docker-compose.yml ps

# control plane
cd control-plane && ./.venv/Scripts/python.exe -m pytest -q     # Windows
cd control-plane && python -m pytest -q                          # WSL (нужен venv 3.12)

# toolchain (WSL)
bash /mnt/c/Users/zarl3/IdeaProjects/ai_dev_project/infra/wsl/bootstrap-toolchain.sh --check
```
