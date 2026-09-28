# Ограничения (M5–M6)

Честный перечень ограничений MVP и текущего состояния. Условия снятия — в `docs/roadmap.md`
(отложенный backlog) и соответствующих ADR.

## Управление и review

- **Solo-mode review.** `required_approving_review_count=0`, `require_code_owner_reviews=false`
  (ADR-0012): владелец вливает PR без независимого human review. Автоматические гейты
  сохранены. Возврат — при появлении второго участника.
- **Staging environment без required reviewer** (ADR-0013): gate обеспечивается независимыми
  проверками (signature/SBOM/provenance + fail-closed `pre-deployment`), а не environment-review.
- **Инструкции — не контроль.** `AGENTS.md`, промпты и любой untrusted-контент (Issue, логи,
  tool output, LLM output) не исполняются как команды; enforcement только out-of-band (ADR-0011).

## Enforcement

- **OPA-точка `pr-ci` не реализована** (реализованы `pre-tool-call`, `artifact-transition`,
  `pre-deployment`). `pr-ci`-решение в release-candidate сейчас проставляется CI, а не policy.
- **Redaction — паттерновая, best-effort.** OTel Collector redacts известные ключи
  (`authorization`, `cookie`, `password|secret|token|api_key`, email). Это не заменяет
  требование не эмитить секреты в атрибуты; экзотические форматы PII могут не покрываться.
- **Алерты без доставки.** Prometheus оценивает правила, но Alertmanager в локальный стек не
  входит — firing виден только в UI/API.
- **Инструментированы gateway и domain.** Publisher/worker пока без OTel-инструментирования.

## Размещение агента и sandbox

- **M1: opencode на Windows host** (ADR-0011) — у агента есть доступ к host; целевое размещение —
  контейнер/devcontainer. Промежуточно — WSL. Полная изоляция sandbox — по мере развития runner.
- **Эфемерность.** Run/capability эфемерны, но постоянный sandbox/runner с полным syscall-ограничением
  ещё не реализован как отдельный сервис.
- **M6: executor in-process.** Runner-executor и tool registry исполняют allowlisted инструменты
  **в процессе** control-plane, а не в изолированном контейнере (ADR-0014). Это слабее изоляции по
  syscalls/egress; нет произвольного shell (только allowlist + schema), но in-process-код агента
  не ограничен на уровне ОС. Контейнерная песочница — в `docs/roadmap.md` (backlog).
- **M6: MCP — in-process + stdio.** MCP-сервер реализован и покрыт in-process-тестами; `sdlc mcp`
  даёт stdio-транспорт. Реальный e2e-прогон внешнего `opencode` против живого OPA — внешнее
  (Docker Desktop / OPA-сервер не запущены в CI).

## Среда и поставка

- **Только local/staging.** Production deployment отложен (нужны стабильный staging, второй
  reviewer, prod-grade secrets) — см. `docs/roadmap.md`.
- **GitHub-зависимость.** Cosign keyless, artifact attestations и provenance привязаны к GitHub
  OIDC; независимый от GitHub provenance — backlog.
- **Без Kubernetes.** Масштабирование/multi-node/autoscaling не поддерживаются (compose-стек).
- **Пины окружения.** control-plane — Python 3.12.x; toolchain зафиксирован в
  `infra/wsl/toolchain.lock`; приложения — Go 1.27, единый модуль `apps`.
- **Границы trust-модели.** Платформа защищает от конкретного класса угроз (prompt-injection,
  неограниченный доступ, подмена supply chain). Это не защита от ошибок в самих policies,
  от compromise GitHub/Keycloak и от side-channel атак на инфраструктуру.
