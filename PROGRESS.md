# PROGRESS

Состояние реализации Secure Agentic SDLC. Самодостаточный handoff: новая сессия/человек
продолжает отсюда, прочитав также `AGENTS.md` и `ARCHITECTURE_BASELINE.md`.

- Обновлено: 2026-09-22
- Текущий milestone: **M1 — Walking skeleton** (начат)
- Предыдущий: **M0 — Фундамент** (завершён)
- Remote: https://github.com/yunecque/ai_dev_project (main, protected)

---

## 1. Статус по milestone

| Milestone | Статус | Примечание |
|---|---|---|
| M0 Фундамент | 100% | завершён; remote + branch protection применены |
| M1 Walking skeleton | ~70% | TASK-0001…0006 done (Go gateway + domain) |
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
cd control-plane
python -m ruff check src tests      # All checks passed
python -m mypy                      # Success: no issues found (5 files, strict)
python -m pytest -q                 # 21 passed
sdlc validate ../specs/examples/*.json   # все OK
sdlc validate ../baseline.json           # OK
```

Все JSON и YAML в репозитории парсятся; compose config валиден.

---

## 4. Что уже в репозитории

```
apps/{gateway,domain,worker}/     # gateway: REST+OIDC+gRPC; domain: gRPC+outbox (Go)
apps/domain/migrations/0001_init.sql  # requests + outbox (pending publisher)
apps/go.mod                       # единый Go-модуль github.com/yunecque/ai_dev_project/apps
apps/gen/domain/v1/               # сгенерированный из proto код (buf, local plugins)
control-plane/                    # Python 3.12: src/sdlc (artifacts, policy, runner, evidence), tests
contracts/schemas/                # 12 JSON Schema (workflow artifacts)
contracts/openapi/requests.yaml   # REST-контракт golden path (OpenAPI 3.1)
contracts/proto/domain/v1/domain.proto  # gRPC-контракт DomainService
contracts/events/                 # request-created.schema.json + examples/
policies/                         # пусто — M1
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
- [ ] **TASK-0007** — outbox publisher → NATS; `apps/worker` идемпотентный consumer.
- [ ] **TASK-0008** — тесты: unit, api_acceptance, authorization, grpc_contract, event_contract,
  integration, security, negative_pipeline, e2e_smoke.
- [ ] **TASK-0009** — реализовать заглушки стадий CI (`contract-tests`, `sast`, `integration-tests`,
  `security-tests`, `policy-check`, `build-image`).

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
