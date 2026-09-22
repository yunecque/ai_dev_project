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

## Модель исполнения и контроля (зафиксированные решения)

Раздел фиксирует договорённости о том, **что** мы строим, **где** это работает и **как**
обеспечивается контроль. Архитектурное обоснование — [ADR-0011](docs/adr/0011-enforcement-boundary-and-agent-placement.md).

### 1. В репозитории — два разных продукта

| # | Продукт | Зона | Роль |
|---|---|---|---|
| **A** | **Платформа** (агентная фабрика) | `control-plane/`, `policies/`, `specs/`, `contracts/` | Главный продукт: валидирует артефакты, запускает агентов, проверяет политики, хранит evidence |
| **B** | **Reference-приложение** | `apps/gateway`, `apps/domain`, `apps/worker` | Маленькое 3-сервисное приложение («заявки») — подопытный кролик golden path, не цель |

### 2. Инструкции — не контроль (enforcement out-of-band)

`AGENTS.md`, промпты и любые инструкции в контексте LLM — **недоверенный, in-band** контент.
Агент может их проигнорировать, переинтерпретировать или быть подтолкнут промпт-инъекцией.
Поэтому контроль **никогда** не строится на послушании агента: он выносится за пределы модели
(GitHub, capability removal, mediation, защищённые зоны).

### 3. Граница контроля: capability removal + mediation + tamper-proofing

Контроль работает только когда у агента **нет альтернативного пути**. Нужны все три слоя:

| Слой | Механизм |
|---|---|
| **Удаление возможностей** | у агента нет прямого сетевого выхода (default-deny egress), нет долгоживущих секретов, только scoped ephemeral token на run, ограниченный mount ФС |
| **Медиация** | единственный интерфейс — MCP-инструменты платформы; OPA `pre-tool-call` (fail-closed) решает allow/deny |
| **Защита от подмены** | `policies/`, `.github/`, `contracts/`, `baseline.json`, `infra/`, `docs/adr/` — защищённые зоны + CODEOWNERS; агент меняет только `apps/` через PR |

| Канал «внешнего мира» | Как закрывается |
|---|---|
| Сеть | default-deny egress + allowlist через прокси |
| Секреты | отсутствуют в контексте/окружении; scoped token |
| ФС вне песочницы | mount только рабочего каталога |
| Процессы / ОС | контейнер/VM с ограниченными syscalls |
| Сама платформа | защищённые зоны + CODEOWNERS + подписи |

### 4. Модель взаимодействия: IDE-агент + платформа

| Слой | Что | Где живёт |
|---|---|---|
| 1. Чат-агент | opencode (TUI/CLI) — интерфейс с человеком; **недоверенный** | Windows host (M1) → контейнер (цель) |
| 2. Платформа | control-plane + OPA + MCP-сервер | host / WSL / Docker |
| 3. Sandbox (runner) | где реально выполняется код и тесты | эфемерный Docker-контейнер |
| 4. Тулчейн | go, python, gh, cosign, trivy, syft, semgrep, gitleaks, buf, uv | WSL или внутри sandbox |

Ключевое: слои независимы. Агент не выполняет код «в проекте на диске» — он просит runner
выполнить в песочнице. `control-plane` — не «стоит между агентом и интернетом», а **заменяет**
агенту интернет узким набором политик-разрешённых инструментов.

**Принятое размещение:** M1 — opencode на Windows host (вариант A, минимум трения);
целевое — opencode внутри devcontainer/песочницы (вариант C, у агента нет доступа к host).
Промежуточный — WSL (паритет с CI).

**Ограничение opencode** (когда платформа управляет проектом, а не строится) — через
`.opencode/`: MCP-сервер платформы + урезанный `permission` (MCP как единственная дверь) +
plugin-хук `tool.execute.before`/`permission.ask` к OPA. Роли из схем (`grill`, `grill-security`,
`planner`, `implementer`, `reviewer`) ложатся на отдельные profiles прав.

### 5. Что реально запускается на устройстве

| Категория | Что | Занимает порты | Обязательно для M1? |
|---|---|---|---|
| Docker-контейнеры | Postgres, NATS, OPA | 5432, 4222/8222, 8181 | да |
| Docker-контейнеры | Keycloak | 8080 | да (auth golden path) |
| Docker-контейнеры | OTel Collector, Prometheus, Grafana, Loki, Tempo | 4317/4318, 9090, 3000, 3100, 3200 | нет — M4 |
| CLI-инструменты (WSL) | go, python, gh, cosign, syft, trivy, semgrep, gitleaks, buf, uv, opa | не занимают | по требованию |
| Наши приложения | gateway/domain/worker (Go) + control-plane (Python) | по мере запуска | M1 |

Для минимального walking skeleton достаточно **Postgres + NATS + OPA**; observability-стек
описан, но не поднимается до M4.

### 6. Открытые вопросы

- **Политика review в solo-mode.** Branch protection требует 1 approving review и
  CODEOWNERS-review, но второй человек отложен в `docs/roadmap.md`. Пока не решено, ни один PR
  не может быть влит. Варианты: добавить второго коллаборанта / временно ослабить требования
  документированным отклонением / отключить `enforce_admins` для solo-владельца.
- **Подтверждение минимального M1-стека** (Postgres + NATS + OPA, Keycloak опционально).

## Governance

- Текущее состояние и handoff: [`PROGRESS.md`](PROGRESS.md).
- Профиль строгости: **strict** (см. `baseline.json`, `ARCHITECTURE_BASELINE.md`).
- Архитектурные решения: `docs/adr/`.
- Roadmap и отложенный backlog: `docs/roadmap.md`.
- Модель evidence: `docs/evidence-model.md`.
- Схемы workflow-артефактов: `contracts/schemas/`.
- Git — единственный source of truth. Markdown генерируется из JSON-артефактов.
- Модель исполнения/контроля и размещение агента: раздел выше + ADR-0011.

## Навигация агента

См. `AGENTS.md` для правил работы с репозиторием и обязательных проверок перед PR.
