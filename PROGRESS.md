# PROGRESS

Состояние реализации Secure Agentic SDLC. Самодостаточный handoff: новая сессия/человек
продолжает отсюда, прочитав также `AGENTS.md` и `ARCHITECTURE_BASELINE.md`.

- Обновлено: 2026-09-24
- Текущий milestone: **M6 — Agent execution layer** (завершён в коде/конфигурации; MVP M0–M5 закрыт)
- Предыдущий: **M5 — Portfolio** (завершён; MVP закрыт)
- Следующий: backlog `docs/roadmap.md` (production, второй reviewer, `pr-ci`, контейнерная песочница)
- Remote: https://github.com/yunecque/ai_dev_project (main, protected)
- Наглядные схемы: `docs/sequences.md` (обновляется по мере прогресса)

---

## 1. Статус по milestone

| Milestone | Статус | Примечание |
|---|---|---|
| M0 Фундамент | 100% | завершён; remote + branch protection применены |
| M1 Walking skeleton | 100% | TASK-0001…0012 done; walking skeleton собран |
| M2 Домен и lifecycle | 100% | TASK-0001…0006 done; feature `FEAT-0002` |
| M3 Supply chain hardening | 100% | TASK-0001…0005 done; feature `FEAT-0003` |
| M4 Staging + observability | 100% | TASK-0001…0006 done; feature `FEAT-0004` |
| M5 Portfolio | 100% | TASK-0001…0003 done; feature `FEAT-0005` |
| M6 Agent execution layer | 100% | TASK-0000…0006 done; feature `FEAT-0006` |

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
python -m mypy                      # Success: no issues found (45 files, strict)
python -m pytest -q                 # 189 passed
sdlc validate ../specs/examples/*.json   # все OK
sdlc validate ../baseline.json           # OK

# apps (Go)
cd apps
gofmt -l . && go vet ./...          # clean
go test ./...                       # unit
go test -tags=integration ./...     # integration (Postgres gated by TEST_DATABASE_URL)

# policy (Rego)
opa fmt --fail policies/ && opa test policies/   # 38/38
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
control-plane/                    # Python 3.12: src/sdlc (artifacts, policy, runner, evidence, waiver, deploy_verify, traceability, tools, llm, skills, mcp, pipeline), tests
.opencode/                        # M6: opencode.json (MCP+permission), plugin/opa-guard.ts, agent/*.md (role profiles)
contracts/schemas/                # 14 JSON Schema (workflow artifacts)
contracts/openapi/requests.yaml   # REST-контракт golden path (OpenAPI 3.1)
contracts/proto/domain/v1/domain.proto  # gRPC-контракт DomainService
contracts/events/                 # request-created.schema.json + examples/
policies/                         # pre_tool_call + artifact_transition + pre_deployment (Rego v1) + tests/
security/{threat-models,tests}/   # пусто — M1
infra/compose/                    # рабочий стек
infra/wsl/                        # bootstrap-toolchain.sh + README + lock
infra/github/                     # apply-branch-protection.ps1 + setup-remote.sh
specs/examples/                   # 12 валидных примеров golden-path
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

1. **Состояние git (handoff).** На `main` **закоммичено** только до `6b18679` (M0–M2, M3
   TASK-0001, документация M3). Всё, что ниже, лежит в **рабочем дереве без коммита** (новый
   session видит файлы на диске):
   - M3 TASK-0002…0005 (`deploy_verify/`, schemas `release-candidate`/`evidence-bundle`,
     `deploy-verify.yml`, ADR-0013, `infra/github/apply-staging-environment.ps1`);
   - M4 (`apps/internal/telemetry/`, observability-конфиги, `prometheus/rules`, dashboards,
     `infra/staging/`, `test_{redaction,observability,alerts,staging}.py`);
   - M5 (`sdlc/traceability.py` + CLI `trace`, `test_{traceability,blocked_attacks}.py`,
     `docs/{security-demos,limitations}.md`, `docs/presentation.html`);
   - M6 план (`docs/m6-agent-execution-layer.md`) и правки PROGRESS/README/sequences/ci.yml/go.mod.
   Проверки на момент handoff: control-plane **150 pytest passed**, ruff/mypy чисто; Go
   gofmt/vet/test зелёные; `sdlc validate` baseline+примеры OK; `sdlc trace FEAT-0001` COMPLETE.
2. **Review-политика решена — ADR-0012:** solo-mode `required_approving_review_count=0` +
   `require_code_owner_reviews=false`; 15 required checks, `enforce_admins`, PR-only и запрет
   force-push сохранены. Возврат к human review — при появлении второго участника.
3. **M3 закрыт (код + конфигурация).** Осталось только внешнее применение/проверка на `main`
   (в PR не проверяется):
   - **`staging` environment** — решено ADR-0013 (solo-mode без required reviewer); применить
     `infra/github/apply-staging-environment.ps1`.
   - Cosign keyless + artifact attestations (TASK-0004) и `deploy-verify` (TASK-0005) выполняются
     только на `push`/`workflow_dispatch` в `main` (GitHub OIDC) → PR CI их не прогоняет,
     проверка постфактум на `main`.
   - GHCR push есть в `build-image` (`packages: write`, на main) — образы доступны
     для scan/SBOM/sign (TASK-0003).
4. **MVP (M0–M5) и M6 закрыты в коде/конфигурации.** Внешнее (постфактум на `main`/вручную):
   применить `infra/github/apply-staging-environment.ps1`; релизные стадии M3
   (sign/attest/deploy-verify) и live-прогон observability против живого стека (Docker Desktop не
   запущен); живой e2e `opencode` через `sdlc mcp` против реального OPA. Дальше — backlog
   `docs/roadmap.md` (production, второй reviewer, `pr-ci`, контейнерная песочница runner).
5. Опционально: `sudo apt install -y python3-venv` (не требуется, semgrep поставлен через `uv`).

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

## 8. Как продолжить (M2 — Домен и lifecycle)

Feature `FEAT-0002`: operator workflow, полная authz-матрица, waiver-механика.

- [x] **TASK-0001** — lifecycle-контракт: state machine (`created→triaged→in_progress→resolved→closed`,
  ветка `cancelled` из `created/triaged/in_progress`), gRPC `UpdateRequestStatus`, событие
  `request-status-changed` (`contracts/events/`), transition-guard в domain + тесты.
  - `apps/domain`: `CanTransition`, `Store.UpdateRequestStatusWithEvent`/`GetRequest`,
    `MemoryStore` + `PostgresStore` (атомарно status + outbox), payload-контракт.
  - `apps/publisher`: маршрутизация событий по типу (`eventSubjects`), fail-closed на неизвестный
    тип; JetStream-стрим `REQUESTS` принимает оба subject'а (`requests.created`,
    `requests.status-changed`).
  - control-plane `test_contracts.py`: схема/пример статус-события, proto RPC (+5 тестов, 75 всего).
- [x] **TASK-0002** — operator workflow API: `GET /requests`, `GET /requests/{id}`,
  `PATCH /requests/{id}/status` (OpenAPI + gateway).
  - [x] proto: `GetRequest`, `ListRequests` RPC; `ListFilter` в domain (`MemoryStore`+`PostgresStore`,
    сортировка newest-first, cap limit); gateway handlers + маппинг gRPC→HTTP
    (`NotFound→404`, `FailedPrecondition→409`, `InvalidArgument→400`, иначе 502).
  - [x] OpenAPI 1.1.0: paths + `RequestStatus`/`UpdateRequestStatus`/`RequestList`; контракт-тесты.
  - [x] тесты: domain query (8), gateway (11), Postgres list (integration), +2 contract (77 всего).
- [x] **TASK-0003** — полная authz-матрица (user/operator, owner-check).
  - Строго по `SPEC-0001`/`TM-0001`: два актёра — **user** (владелец) и **operator**; `admin` нет,
    OPA для runtime REST не вводится (ADR-0004 точки — только platform).
  - gateway: `tokenVerifier` возвращает `identity{subject, roles}` (Keycloak `realm_access.roles`),
    `roleOf` сводит к user/operator; PATCH требует operator (иначе 403); actor context
    (subject+role) уходит в domain.
  - domain: `GetRequest` — чужой id у не-operator → **404** (без утечки существования, CTRL-0001);
    `ListRequests` — не-operator видит только свои; `UpdateRequestStatus` — только operator
    (`PermissionDenied`); отсутствие identity context → `InvalidArgument` (CTRL-0002).
  - тесты: domain authz (11), gateway (14), proto/OpenAPI 403; `authorization_test.go` обновлён.
- [x] **TASK-0004** — waiver-механика.
  - `control-plane/src/sdlc/waiver/`: `is_waivable` (только Medium), `may_manage_waiver`
    (только human; agent/ci — нет), `validate_waiver` (approver = security-reviewer,
    separation of duties owner≠approver, expiry>created), `waiver_state`, `check_waiver`,
    `evaluate_risk` (Critical/High — всегда блок; Medium — только по active waiver; Low —
    не блок; unknown severity — fail-closed).
  - CLI: `sdlc waiver <path> [--now]` (schema + семантика, exit 1 при блоке).
  - CI: `security-tests` теперь включает `test_waiver.py`.
  - Тесты: `tests/test_waiver.py` (22); всего 99 passed.
- [x] **TASK-0005** — OPA точка `artifact-transition`.
  - `policies/artifact_transition.rego` (Rego v1): таблицы статусов/переходов для
    `specification`, `threat-model`, `plan`, `task`, `waiver`; deny с reason codes —
    `UNKNOWN_ARTIFACT_TYPE`, `UNKNOWN_STATUS`, `ILLEGAL_TRANSITION`,
    `AGENT_MAY_NOT_APPROVE`, `BLOCKING_FINDING` (critical/high), `UNRESOLVED_MEDIUM`
    (medium без active+unexpired waiver), fail-closed без `now`.
  - `policies/tests/artifact_transition_test.rego` — 16 тестов (opa test: 23/23 всего).
  - control-plane `sdlc.policy.artifact_transition`: `build_transition_input`,
    `evaluate_transition`, `build_transition_decision` (point `artifact-transition`).
  - CI `security-tests` включает `test_artifact_transition.py`; всего 104 passed.
- [x] **TASK-0006** — e2e operator-flow, обновление `docs/sequences.md` и `PROGRESS.md`.
  - worker `Handler` принимает оба типа событий (`request-created`, `request-status-changed`).
  - `domain` integration: `TestOperatorLifecycleFlowIntegration` — create → 4 перехода → read-back,
    outbox ровно `1` created + `4` status-changed.
  - worker e2e: `TestStatusChangedEventSmoke` — канонический пример через embedded JetStream,
    ровно один раз.
  - docs: `sequences.md` (M2 ✅, e2e, точки policy), `PROGRESS.md` (M2 закрыт).

## 9. Как продолжить (M3 — Supply chain hardening)

Feature `FEAT-0003`: Cosign keyless, SBOM/attestations, независимый `deploy-verify`.

- [x] **TASK-0001** — OPA точка `pre-deployment` (independent release gate).
  - `policies/pre_deployment.rego` (Rego v1): требует image, verified signature, present SBOM,
    verified provenance, allow-решения `artifact-transition`+`pr-ci` и human-approval роли
    `required_approver_role`; agent-approval не считается; fail-closed.
  - `policies/tests/pre_deployment_test.rego` — 12 тестов (opa test: 35/35 всего).
  - `control-plane/src/sdlc/policy/pre_deployment.py` + `test_pre_deployment.py` (4).
  - Осталось: реальные `container-scan`/`sbom-generate`/`sign-and-attest` и verification
    в `deploy-verify` (нужны GHCR push + environment reviewer).
- [x] **TASK-0002** — control-plane `deploy_verify`: release candidate → evidence bundle → policy.
  - Контракт: `contracts/schemas/release-candidate.schema.json`,
    `contracts/schemas/evidence-bundle.schema.json` + примеры в `specs/examples/`.
  - `control-plane/src/sdlc/deploy_verify/`: `candidate.py` (schema-валидация untrusted входа,
    canonical JSON + SHA-256), `bundle.py` (контент-адресуемый evidence bundle:
    `kind`/`ref`/`digest`, `bundle_digest`), `verify.py` (`verify_release` — bundle +
    `pre-deployment` OPA + `policy-decision` со ссылкой на bundle).
  - CLI `sdlc deploy-verify <candidate.json> [--opa-url|--output-dir|--now|...]`, exit 1 при deny.
  - CI `policy-check`: self-test на реальной политике (OPA server + пример allow).
  - Тесты `tests/test_deploy_verify.py` (11); всего 119 passed.
- [x] **TASK-0003** — Syft SBOM + Trivy container-scan + GHCR push на main.
  - `.github/workflows/ci.yml`: `build-image` логинится в GHCR (`packages: write`) и на
    `push` в `main` публикует `ghcr.io/<owner>/<repo>/{gateway,domain,publisher,worker}:$GITHUB_SHA`
    (теги в нижнем регистре); на PR — только сборка.
  - `container-scan`: `needs: build-image`, на main логин в GHCR + `trivy image
    --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1` по каждому образу.
  - `sbom-generate`: `needs: build-image`, на main скачивает Syft v1.52.0 и генерирует
    SPDX-JSON SBOM по каждому образу в artifact `sbom` (retention 30 дней).
  - Все 15 job-имён сохранены (branch protection required checks не затронуты);
    YAML парсится.
- [x] **TASK-0004** — Cosign keyless sign + artifact attestations на main (GitHub OIDC).
  - `sign-and-attest` (permissions: `packages: write`, `id-token: write`,
    `attestations: write`): логин в GHCR, Cosign v3.1.3 через `sigstore/cosign-installer@v4.1.0`,
    `cosign sign --yes` по каждому образу (keyless OIDC), затем `actions/attest@v4` —
    SLSA build provenance и SBOM (SPDX-JSON из artifact `sbom`) для каждого образа,
    `push-to-registry: true`.
  - Digest каждого образа резолвится `docker buildx imagetools inspect` и сохраняется в
    artifact `image-digests` (`image-digests.json`) — вход для `deploy-verify` (TASK-0005).
  - Выполняется только на `push` в `main` (OIDC), в PR не проверяется — постфактум на `main`.
- [x] **TASK-0005** — `deploy-verify.yml`: реальные шаги, `staging` environment, ADR-0013.
  - `deploy-verify.yml` (workflow_dispatch, вход `image` + опц. `image_digest`): job'ы
    `verify-signature` (`cosign verify` keyless, identity-regexp ci.yml@main), `verify-sbom`
    (`cosign verify-attestation --type spdxjson`), `verify-provenance`
    (`gh attestation verify oci://…`), `verify-policy-and-approvals` (`environment: staging`,
    сборка release-candidate через `jq`, OPA `pre-deployment` сервер + `sdlc deploy-verify`,
    artifact `deploy-evidence`). Проверки независимы от build/sign job.
  - ADR-0013: solo-mode `staging` без required reviewer (иначе deadlock self-approval);
    gate = обязательные независимые проверки + fail-closed policy; возврат к reviewer при
    втором участнике. `docs/branch-protection.md` обновлён.
  - `infra/github/apply-staging-environment.ps1` — создаёт environment `staging`
    (protected branches = main, без reviewers).
  - `workflow_dispatch`-гейт не проверяется в PR — запуск/проверка постфактум на `main`.

## 10. Как продолжить (M4 — Staging + observability)

Feature `FEAT-0004`: OTel-инструментирование, redaction, dashboards/alerts, mini PC staging.

- [x] **TASK-0001** — OTel traces/metrics golden path + context propagation.
  - `apps/internal/telemetry`: `Setup` (resource `service.name`, OTLP gRPC trace/metric exporters
    только при `OTEL_EXPORTER_OTLP_ENDPOINT`, иначе no-op; W3C TraceContext+Baggage propagator),
    `HTTPHandler` (otelhttp), `GRPCServerOption`/`GRPCClientOption` (otelgrpc stats handlers).
  - gateway: HTTP-сервер обёрнут в `telemetry.HTTPHandler`, gRPC-клиент с `telemetry.GRPCClientOption`.
    domain: gRPC-сервер с `telemetry.GRPCServerOption`; trace-context прокидывается gateway→domain.
  - deps: `otel v1.46.0`, `otelhttp`/`otelgrpc v0.71.0`; `apps/go.mod`/`go.sum` обновлены.
  - Тесты `apps/internal/telemetry/telemetry_test.go` (3): Setup без endpoint, HTTP server span,
    gRPC trace propagation через bufconn. `gofmt`/`go vet`/`go test ./...` зелёные.
- [ ] **TASK-0002** — redaction в Collector + тесты отсутствия sensitive-полей в телеметрии.
- [x] **TASK-0002** — обязательная redaction телеметрии + guard-тесты.
  - `infra/compose/otel-collector.yaml`: `transform/redact` теперь подключён во **все** сигналы
    (traces/metrics/logs) и идёт до `batch`; metric-контекст (`datapoint`) добавлен. Redaction:
    `authorization`/`cookie`/`set-cookie` атрибуты → `[REDACTED]`; тело лога —
    secret/token/password/api-key → `$1=[REDACTED]`; email (PII) → `[REDACTED_EMAIL]`.
  - Исправлен скрытый баг: значения statements — plain-скаляры YAML, поэтому `\\s`/`\\S` в
    старом конфиге попадали в OTTL как двойной бэкслеш (redaction тела лога фактически не
    работала). Теперь одинарные `\s`/`\S`/`\.`.
  - `control-plane/tests/test_redaction.py` (4): redact во всех пайплайнах (и до batch), наличие
    контекстов trace/metric/log, обязательные паттерны, поведенческий реплей `replace_pattern`
    на sample-телеметрии (секреты/PII удалены, не-sensitive сохранён).
  - CI `security-tests` включает `test_redaction.py`.
- [ ] **TASK-0003** — Prometheus метрики + Grafana dashboards (provisioning).
- [x] **TASK-0003** — Prometheus метрики + Grafana dashboards (provisioning).
  - `infra/compose/otel-collector.yaml`: Prometheus exporter c
    `resource_to_telemetry_conversion.enabled=true` → `service_name` становится меткой
    (нужно для панелей по сервисам).
  - `grafana/provisioning/datasources/datasources.yaml`: детерминированные `uid`
    (`prometheus`/`loki`/`tempo`).
  - `grafana/provisioning/dashboards/dashboards.yaml` (file-provider) +
    `dashboards/golden-path.json`: панели — request rate, HTTP p95, 5xx ratio, gRPC rate,
    `up` (datasource uid зафиксированы).
  - `control-plane/tests/test_observability.py` (5): scrape otel-collector:8889, resource-conversion,
    uids, dashboard provider, валидность dashboard (панели/targets/expr/datasource).
  - Live-валидация конфига коллектора (`otelcol-contrib validate`) не выполнена — Docker Desktop
    не запущен; проверено статически (YAML + guard-тесты).
- [ ] **TASK-0004** — alert rules (SLO golden path).
- [x] **TASK-0004** — Prometheus alert rules (SLO golden path).
  - `infra/compose/prometheus/rules/golden-path.yml`: `GoldenPathServiceDown` (critical,
    up{job="otel-collector"}==0, 5m), `GoldenPathHighErrorRate` (warning, 5xx ratio >5%, 10m),
    `GoldenPathHighLatency` (warning, p95 >1s, 10m), `GoldenPathNoRequests` (info, 30m).
  - `prometheus.yml`: `rule_files` → `/etc/prometheus/rules/*.yml`; compose монтирует
    `./prometheus/rules`.
  - `control-plane/tests/test_alerts.py` (4): rule_files подключены, mount есть, все алерты
    well-formed (expr/for/severity/summary/description), обязательные алерты и severity.
  - Доставка алертов требует Alertmanager (в локальный стек не входит) — Prometheus оценивает,
    UI показывает firing.
- [x] **TASK-0005** — mini PC staging (compose/systemd) + docs.
  - `infra/staging/docker-compose.yml`: приложения из GHCR
    (`${IMAGE_REGISTRY}/{gateway,domain,publisher,worker}:${IMAGE_TAG}`) + инфраструктура;
    конфиги наблюдаемости переиспользуются из `infra/compose/` (единый источник).
  - `migrate` (postgres:16-alpine, `restart: "no"`) применяет `0001_init.sql` +
    `0002_processed_events.sql` идемпотентно; `domain`/`publisher`/`worker` ждут
    `service_completed_successfully`.
  - `restart: unless-stopped`, named volumes, наружу только 8081/3000/9090/3100/3200.
  - `infra/staging/.env.example` (только CHANGE_ME), `deploy.sh`, `systemd/secure-agentic-sdlc.service`,
    `README.md` (порядок релиза через `deploy-verify`, ADR-0013).
  - `control-plane/tests/test_staging.py` (9): сервисы, pinned GHCR-образы, restart-политики,
    migrations-gate, OTel env, переиспользование конфигов, systemd, отсутствие секретов.
  - Реальное развёртывание на mini PC — внешнее (артефакты статически проверены).
- [x] **TASK-0006** — e2e observability smoke + docs.
  - `apps/internal/telemetry/telemetry_test.go`: `TestGoldenPathObservabilitySmoke` — HTTP-хендлер
    (otelhttp) вызывает gRPC-бэкенд (otelgrpc) через bufconn; ровно один trace, server-спаны на
    обоих хопах + client-спан, и значение `Authorization` не попадает в атрибуты спанов.
  - `docs/sequences.md`: новый §6 «Observability pipeline (M4)» (диаграмма + refs), статусы
    M3 ✅ / M4 ⏳, таблица milestone обновлена.
  - `PROGRESS.md`: M4 закрыт.
  - Прогон против живого стека (Collector/Tempo/Prometheus) — внешнее (Docker Desktop не запущен);
    app-уровень e2e проверен `go test`.

## 11. Как продолжить (M5 — Portfolio)

Feature `FEAT-0005`: traceability, демонстрации заблокированных атак, ограничения.

- [x] **TASK-0001** — traceability chain.
  - `control-plane/src/sdlc/traceability.py`: `trace_feature` строит граф `links` (в обе стороны —
    reviews/evidence ссылаются на цепочку), находит недостающие стадии (`CHAIN_ORDER`) и висячие
    локальные `.json`-ссылки; `format_report`.
  - CLI `sdlc trace --feature FEAT-0001 [--json] [--repo-root]`, exit 1 при неполной цепочке.
  - `tests/test_traceability.py` (5): полная цепочка FEAT-0001, missing stage, dangling link, CLI.
- [x] **TASK-0002** — 4 демонстрации заблокированных атак.
  - `tests/test_blocked_attacks.py` (4): prompt-injection + sensitive exfiltration; подделка/повтор/
    scope/истечение capability; запрет agent/CI approval и waiver; Critical/High never-waived +
    просроченный waiver снова блокирует. `docs/security-demos.md` (attack → control → test/opa).
- [x] **TASK-0003** — ограничения и README.
  - `docs/limitations.md` (solo-mode, in-band не контроль, `pr-ci` не реализована, best-effort
    redaction, Alertmanager, размещение агента, GitHub-зависимость, без K8s).
  - README раздел «Portfolio: traceability и демонстрации»; `docs/sequences.md` — все milestone ✅.

## 12. M6 — Agent execution layer (завершён)

Feature `FEAT-0006`. Слой «агент, который проходит идею → фичу под управлением платформы».
Основание — ADR-0014 (и ADR-0011), полный план — `docs/m6-agent-execution-layer.md`.

- [x] **TASK-0000** — ADR-0014 «Agent execution layer» + пункт M6 в `docs/roadmap.md`
  (+ backlog: контейнерная песочница). ADR-индекс обновлён.
- [x] **TASK-0001** — tool registry + runner-executor.
  - `src/sdlc/tools/`: `ToolRegistry`/`ToolSpec` (scope + inline JSON-схемы args/result),
    `UnknownToolError`, `validate_instance`, `make_tool`.
  - `src/sdlc/runner/executor.py`: `RunnerExecutor.execute` — OPA `pre-tool-call` → capability →
    lookup → scope → args/result schema → handler; на каждый вызов `policy-decision` +
    `evidence-record` (untrusted, `policy_decision_ref`); actor берётся из run, не от caller;
    любой handler-сбой → `EXECUTION_FAILED` (fail-closed).
  - Тесты `test_tools.py` (4), `test_executor.py` (6); 170 passed (было 150).
- [x] **TASK-0002** — LLM adapter + skill `task-writer`.
  - `src/sdlc/llm/`: `LLMAdapter` Protocol, `LLMRequest`/`LLMResponse`, `StubLLM` (fail-closed на
    неизвестную роль).
  - `src/sdlc/skills/`: `Skill` (prompt+contract), `build_context` (sensitive → ошибка),
    `extract_json` (untracked-текст как data), `SkillRunner` (policy+capability+evidence);
    `TaskWriter` собирает canonical `task`, инъекции LLM-полей игнорируются, статус `todo`.
  - Тесты `test_skills.py` (8).
- [x] **TASK-0003** — остальные role skills: `grill`→specification, `grill-security`→threat-model,
  `planner`→plan, `reviewer`→review (`src/sdlc/skills/roles.py`, `build_default_registry`).
  Тесты +5 (в `test_skills.py`).
- [x] **TASK-0004** — MCP server (`src/sdlc/mcp/`): минимальный JSON-RPC 2.0 (`initialize`,
  `tools/list`, `tools/call`), capability-auth, делегирование в executor, fail-closed
  (bad capability → RPC error; deny → tool error), `InProcessClient`. Тесты `test_mcp.py` (7).
- [x] **TASK-0005** — `.opencode/` интеграция (защищённая зона): `opencode.json` (MCP
  `sdlc-platform`, `permission` deny для edit/bash/сети, read-guard sensitive), plugin
  `plugin/opa-guard.ts` (`tool.execute.before`/`permission.ask` → OPA), 6 role profiles; плюс
  builtin artifact-tools + CLI `sdlc mcp` (stdio). Тесты `test_opencode_config.py` (6).
- [x] **TASK-0006** — pipeline orchestrator (`src/sdlc/pipeline/`): e2e `idea→…→review` на
  stub-агенте, каждый шаг policy+capability+evidence, детерминированный `security-review`,
  финальный `trace_feature` = COMPLETE. Тесты `test_pipeline.py` (3); docs обновлены.

Итог: 189 pytest (ruff/mypy clean), opa test 38/38 (allowlist расширен M6-tools/skills),
Go gofmt/vet/test зелёные. Внешнее (постфактум): живой e2e `opencode` против реального OPA
(см. `docs/limitations.md`).

Критерии приёмки: агент через MCP проводит срез `idea→task` с policy/evidence на каждом шаге;
артефакты schema-valid; `sdlc trace --feature …` = COMPLETE; sensitive вне контекста; агент не
утверждает артефакты/релизы; неизвестный tool / нет capability / policy недоступна — fail-closed.

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
