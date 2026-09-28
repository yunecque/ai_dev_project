# Handoff: opencode ↔ OPA (состояние правок)

Продолжение работы: прочитай этот файл + `docs/faq-opencode-opa.md`,
`docs/runbook-agent-stack.md`, `docs/pr-plan-opencode-opa.md`, `docs/plan-open-pr-tool.md`,
`docs/plan-sandbox-publish.md`.

## Что сделано
1. OPA: политики снова грузятся (импорт keyword'ов; тесты не монтируются в сервер).
2. `.opencode/plugin/opa-guard.ts`: маппинг нативных тулз в словарь политики
   (`read→read_file`, `write/edit→write_file`, `glob/grep→list_files`, `skill→skill.<name>`),
   нормализация Windows-путей (`\`→`/`).
3. `policies/pre_tool_call.rego`: новый гейт `PROTECTED_PATH` (запрет прямого `write_file`
   в защищённые зоны) + тесты.
4. `.opencode/opencode.json` восстановлен по контракту; `permission.edit=deny` (MCP — единая
   дверь).
5. Панельные tools (вариант B): `write_file` (path-confined в `--root`), `run_tests`
   (allowlist ruff/mypy/pytest/opa/gofmt/go, `shell=False`, таймаут, `cwd`, обрезка вывода),
   capability bootstrap в stdio-мосте (`mcp/bootstrap.py`), executor прокидывает `path` в OPA
   как `resource`.
6. Тесты: `test_tools`, `test_commands`, `test_executor`, `test_mcp`.
7. Документы: FAQ по инциденту, runbook, план PR.
8. **Разбор обрыва MCP**: stdio-мост форсит UTF-8 и переживает плохой запрос —
   `cli.serve_stdio` + `tests/test_stdio.py`.
9. **`open_pr` (TASK-0009)**: панельная policy-gated тула —
   `control-plane/src/sdlc/tools/vcs.py`; регистрация в `cli._cmd_mcp` (scope `vcs`, только при
   `SDLC_GITHUB_TOKEN`); executor отдаёт `resource` и из `args["paths"]`; `tests/test_vcs.py`.
10. **План песочницы + публикации** (TASK-0010): `docs/plan-sandbox-publish.md` — песочница
    `sandbox/` вне публичного репо (`.gitignore` + OPA-guard), тула `publish_app` создаёт
    отдельный (private) repo и публикует приложение.

## Почему MCP «отваливался», хотя был активен
Симптом: `Connection closed` на панельном `write_file` при теле >~4 КБ; не-ASCII документы
сохранялись кракозябрами (`Р°РіРµРЅС‚СЃРєРёР№`). Диагноз:

- `cli._cmd_mcp` читал/писал stdio в **текстовом режиме с кодировкой локали Windows**
  (cp1251), а не UTF-8, и **не имел `try/except`** вокруг обработки строки. Любое исключение
  в `server.handle_line(...)` — `UnicodeEncode/DecodeError` на не-ASCII, `BrokenPipeError` —
  выходило из `for line in sys.stdin`, процесс завершался, и opencode показывал
  `Connection closed` при формально поднятом транспорте.
- `mcp/server.py` отдаёт `json.dumps(..., ensure_ascii=False)` → ответ писался прямо в
  cp1251-stdout.
- Подтверждение: `docs/runbook-agent-stack.md`, `docs/pr-plan-opencode-opa.md` и файл в
  `specs/evidence/` были записаны UTF-8-байтами с дампом через cp1251 (двойная перекодировка).

Фикс: `cli.serve_stdio` (`src/sdlc/cli.py`):
- `_force_utf8` переводит stdin/stdout в UTF-8 (`errors=replace`), no-op для StringIO;
- каждый запрос в `try/except` → при сбое отдаёт JSON-RPC `INTERNAL_ERROR` (fail-closed), но
  сервер жив.

## Проверено (эта сессия, через панельный `run_tests`, cwd=control-plane)
- `ruff check src tests` ✅ · `mypy` ✅ (48 файлов) · `pytest -q` ✅ **219 passed**.
- e2e кодировки: `write_file` через живой MCP с кириллицей **4545 Б** (>4 КБ) → прочитано
  байт-в-байт UTF-8, обрыва нет.
- `test_opencode_config.py` ✅ (`"edit": "deny"`).
- Живой MCP-пробник: `OPEN_PR_REGISTERED: True`, но `TOKEN_PRESENT: False` → `open_pr` не
  активирован (нужны env + рестарт).

## Изменённые файлы (текущая сессия)
- functional: `control-plane/src/sdlc/cli.py` (`serve_stdio`, `_force_utf8`, регистрация
  `open_pr`), `control-plane/src/sdlc/tools/vcs.py` (новый),
  `control-plane/src/sdlc/tools/__init__.py`, `control-plane/src/sdlc/runner/executor.py`
- tests: `control-plane/tests/test_stdio.py`, `control-plane/tests/test_vcs.py` (новые)
- config (пользователем): `.opencode/opencode.json` — `permission.edit` → `deny`
- docs: `docs/handoff-opencode-opa.md`, `docs/runbook-agent-stack.md`,
  `docs/pr-plan-opencode-opa.md`, `docs/faq-opencode-opa.md`, `docs/plan-open-pr-tool.md`,
  `docs/plan-sandbox-publish.md`

## Открыто / известные ограничения
- **Активация `open_pr`**: задать `SDLC_GITHUB_TOKEN` + `SDLC_GITHUB_REPOSITORY` в окружении
  запуска opencode и перезапустить; push требует настроенного git-доступа (credential manager).
- **Политика для `open_pr`/`publish_app`** (`PROTECTED_PR_PATH`, `SANDBOX_PR_DENY`,
  `PRIVATE_REPO_REQUIRED`) — protected zone, нужен CODEOWNERS-PR.
- **Песочница/публикация** — только план (`docs/plan-sandbox-publish.md`), код не начат.
- `.opencode/README.md` — патч в PR #1 (защищённая зона).
- `opa test policies/` — в WSL (ожидается 42/42 + новые кейсы).
- `permission.edit=deny`: агент меняет файлы **только** через панельный `write_file`
  (сначала `read`, правка — целым файлом; protected-зоны — только PR).

## Как продолжить
1. Поднять стек и PATH (runbook §2), запустить opencode — MCP поднимется сам.
2. В новой беседе: «прочитай docs/handoff-opencode-opa.md и связанные docs; продолжай».
3. Проверки — через `run_tests` с `cwd=control-plane`.
4. Коммиты — по `docs/pr-plan-opencode-opa.md`; защищённые зоны → CODEOWNERS.
