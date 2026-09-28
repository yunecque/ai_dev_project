# Runbook: агентский стек (opencode ↔ MCP ↔ OPA)

## Запуск
1. `docker compose -f infra/compose/docker-compose.yml --env-file infra/compose/.env up -d`
2. Один раз добавить venv в PATH пользователя:
   `C:\Users\zarl3\IdeaProjects\ai_dev_project\control-plane\.venv\Scripts`
3. Запустить opencode — он сам поднимает MCP `sdlc mcp` (stdio, отдельный демон не нужен).

## Проверка статуса
- `docker ps --filter name=opa`
- `curl.exe http://localhost:8181/health` и `/v1/data` (непустой JSON = политики загружены)
- `where.exe sdlc` ; `ruff --version`
- MCP smoke: `'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | sdlc.exe mcp --root C:\Users\zarl3\IdeaProjects\ai_dev_project`
- `Get-Process sdlc` (пока opencode открыт)
- OPA-тесты (WSL): `wsl bash -lc "cd /mnt/c/Users/zarl3/IdeaProjects/ai_dev_project && opa test policies/"`

## Проверки кода (через run_tests, cwd=control-plane)
`ruff check src tests` ; `mypy` ; `pytest -q`

## Перезапуски
- `policies/*.rego` → рестарт контейнера OPA (не читает политики на лету)
- код control-plane / `plugin/opa-guard.ts` / `.opencode/opencode.json` → перезапуск opencode

## Частые сбои
- `POLICY_UNAVAILABLE` — OPA не слушает :8181
- `TOOL_NOT_IN_ALLOWLIST` — нет маппинга имени тулзы
- `MCP error -32000` — `sdlc` не в PATH / MCP упал
- `PROTECTED_PATH` — запись в защищённую зону (только PR)
- `SENSITIVE_PATH` на Windows — путь нормализуется в плагине (`\`→`/`)
- `Connection closed` при большом/не-ASCII `write_file` — кодировка stdio (см. `docs/faq-opencode-opa.md`)

## Границы
- нет bash: только allowlisted `run_tests` (ruff/mypy/pytest/opa/gofmt/go)
- нет прямого edit: запись только панельным `write_file`
- защищённые зоны (`policies/`, `.opencode/`, `.github/`, `contracts/`, `specs/`, `infra/`,
  `security/`, `docs/adr/`, `docs/roadmap.md`, `baseline.json`, `ARCHITECTURE_BASELINE.md`) —
  только PR с CODEOWNERS
- git/PR — вручную (`open_pr` не реализован)

Подробный разбор инцидента и обоснования — в `docs/faq-opencode-opa.md`.
