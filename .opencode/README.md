# `.opencode/` — ограничение IDE-агента

Защищённая зона (CODEOWNERS). Реализует слой M6/ADR-0011/ADR-0014: агент `opencode` физически не
имеет прямого доступа к shell/ФС/сети и работает только через платформенные MCP-инструменты.

## Что здесь

| Файл | Назначение |
|---|---|
| `opencode.json` | регистрация MCP-сервера `sdlc-platform`, урезанный `permission`, plugin |
| `plugin/opa-guard.ts` | хук `tool.execute.before` / `permission.ask` → OPA `pre-tool-call` (fail-closed) |
| `agent/<role>.md` | role profiles: `grill`, `grill-security`, `planner`, `task-writer`, `implementer`, `reviewer` |

## Принципы

- **MCP — единственная дверь.** `permission.edit=bash=webfetch=websearch=deny`,
  `external_directory=deny`; изменения идут через `read_artifact`/`write_artifact`/`open_pr`.
- **OPA-гейт.** Plugin проверяет каждый прямой tool-вызов против `pre-tool-call`; недоступная
  или deny-policy → действие блокируется.
- **Роли = profiles.** Каждая роль имеет свой профиль прав и работает через skill-контракт.
- **Утверждения — только human.** Агент не апрувит артефакты/релизы и не управляет waiver.

## MCP-сервер

`opencode.json` запускает `sdlc mcp` (stdio). Сервер требует capability-аутентификацию; окружение
платформа прокидывает заранее:

| Переменная | Значение |
|---|---|
| `OPA_URL` | адрес OPA (по умолчанию `http://localhost:8181`) |
| `SDLC_MCP_SECRET` | hex-encoded HMAC-секрет capability-токенов |
| `SDLC_RUN_ID` | id эфемерного run, зарегистрированного платформой |
| `SDLC_ACTOR_JSON` | actor run (по умолчанию agent/opencode/implementer) |

`tools/call` дополнительно требует `run_id`, `token`, `scope` (capability). Без валидного
capability и allow-решения OPA вызов отклоняется.

## Изменения конфигурации

Config загружается один раз при старте opencode. После правок — перезапустить opencode.