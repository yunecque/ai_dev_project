# План PR: opencode/OPA hardening + панельные tools

Конвенция AGENTS.md: один PR — одна задача; защищённые зоны требуют CODEOWNERS-ревью.

## PR #1 — защита (protected zones + guard)
- ветка: `feature/FEAT-0006-TASK-0005-opencode-guard-hardening`
- commit: `FEAT-0006/TASK-0005: enforce protected zones and normalize paths in pre-tool-call guard`
- файлы: `policies/pre_tool_call.rego`, `policies/tests/pre_tool_call_test.rego`,
  `.opencode/plugin/opa-guard.ts`, `.opencode/opencode.json`, `.opencode/README.md`,
  `docs/faq-opencode-opa.md`
- зачем: фикс ложного deny (несовпадение имён тулз), нормализация Windows-путей (маркеры
  `secrets/`,`credentials/`), новый гейт `PROTECTED_PATH`.
- тест-план: `opa test policies/` 42/42; `read` обычного файла → allow; `read .env` →
  `SENSITIVE_PATH`; `write policies/…` → `PROTECTED_PATH`.

## PR #2 — панельные write_file/run_tests
- ветка: `feature/FEAT-0006-TASK-0007-panel-write-run-tools`
- commit: `FEAT-0006/TASK-0007: add panel write_file/run_tests with capability bootstrap`
- файлы: `control-plane/src/sdlc/tools/{builtin.py,commands.py,__init__.py}`,
  `runner/executor.py`, `mcp/bootstrap.py`, `cli.py`,
  `tests/test_{tools,commands,executor,mcp}.py`, `docs/runbook-agent-stack.md`
- зачем: агент пишет код и гоняет проверки через MCP без shell; путь идёт в OPA как `resource`.
- тест-план: `ruff`/`mypy`/`pytest` → 219 passed; `bash` → `TOOL_NOT_IN_ALLOWLIST`;
  запись в `policies/` → `PROTECTED_PATH`; `../` → ValueError; `cwd` escape → ValueError.

## PR #3 — устойчивый UTF-8 stdio-мост
- ветка: `feature/FEAT-0006-TASK-0008-stdio-utf8-robustness`
- commit: `FEAT-0006/TASK-0008: force UTF-8 and survive bad requests in stdio MCP bridge`
- файлы: `control-plane/src/sdlc/cli.py`, `control-plane/tests/test_stdio.py`,
  `docs/faq-opencode-opa.md`, `docs/runbook-agent-stack.md`, `docs/pr-plan-opencode-opa.md`
- зачем: MCP-мост читал/писал stdio в кодировке локали Windows (cp1251) → искажение не-ASCII и
  падение на >~4 КБ (`Connection closed`).
- тест-план: ✅ `pytest`; ✅ e2e `write_file` с кириллицей 4545 Б — файл байт-в-байт UTF-8.

## PR #4 — панельный `open_pr` (агент готовит PR)
- ветка: `feature/FEAT-0006-TASK-0009-open-pr-tool`
- commit: `FEAT-0006/TASK-0009: add policy-gated open_pr tool for agent-authored PRs`
- файлы (функц.): `control-plane/src/sdlc/tools/vcs.py` (новый),
  `control-plane/src/sdlc/tools/__init__.py`, `control-plane/src/sdlc/cli.py`,
  `control-plane/src/sdlc/runner/executor.py`, `control-plane/tests/test_vcs.py`,
  `docs/plan-open-pr-tool.md`
- файлы (защищённая часть, CODEOWNERS): `policies/pre_tool_call.rego`,
  `policies/tests/pre_tool_call_test.rego` — гейт `PROTECTED_PR_PATH` для `open_pr`.
- тест-план: ✅ `pytest tests/test_vcs.py` (8), `ruff`, `mypy` (48), `pytest` 219 passed;
  ⛔ `opa test` — после рего-правки.

## PR #5 — песочница + `publish_app` (плана: `docs/plan-sandbox-publish.md`)
- ветка: `feature/FEAT-0006-TASK-0010-sandbox-publish-app`
- commit: `FEAT-0006/TASK-0010: add sandbox isolation and publish_app tool`
- файлы (функц.): `control-plane/src/sdlc/tools/publish.py` (новый), `tools/__init__.py`,
  `cli.py`, `runner/executor.py`, `tests/test_{publish,sandbox}.py`, **`.gitignore`**
  (`/sandbox/`), `docs/plan-sandbox-publish.md`
- файлы (protected, CODEOWNERS): `policies/pre_tool_call.rego`, `policies/tests/…` — правила
  `SANDBOX_PR_DENY`, `PRIVATE_REPO_REQUIRED`, allowlist `publish_app`.
- зачем: агент пишет приложение в песочнице (не попадает в публичный repo панели) и публикует
  в отдельный private GitHub-репозиторий через policy-gated тулу.
- тест-план: `pytest tests/test_{publish,sandbox}.py`; `.gitignore` содержит `/sandbox/`;
  sandbox→панельный `open_pr` → deny; `source` вне sandbox → отказ; public без allow → отказ.

## Порядок
1. PR #3 (stdio-фикс) — проверен, независим.
2. PR #4 функц. → protected-часть (политика) с CODEOWNERS.
3. PR #5 функц. (`publish_app` + `.gitignore`) → protected-часть (политика) с CODEOWNERS.
4. PR #1 (guard/config) и PR #2 (панельные tools) — по готовности.

## Открытые пункты / ограничения
- Активация `open_pr`: `SDLC_GITHUB_TOKEN` + `SDLC_GITHUB_REPOSITORY` в env + рестарт; push
  требует настроенного git-доступа (credential manager).
- Токен: scoped GitHub App token vs PAT — решить (ADR) до продакшена; для `publish_app` scope
  шире (создание репо).
- `.opencode/README.md` — патч в PR #1 (защищённая зона).
- `run_tests` allowlist: ruff/mypy/pytest/opa/gofmt/go; произвольного shell нет.
