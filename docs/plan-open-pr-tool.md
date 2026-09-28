# План среза: панельная тула `open_pr` (агент готовит PR сам)

Идея: агент не получает git/shell, но может провести срез `contract → code → test` до PR
через **policy-gated панельную тулу** `open_pr`. Дверь уже открыта в политике
(`policies/pre_tool_call.rego:11` — `open_pr` в `allowed_tools`).

- Feature: `FEAT-0006` (agent execution layer), Task: `TASK-0009`
- Ветка: `feature/FEAT-0006-TASK-0009-open-pr-tool`
- Commit: `FEAT-0006/TASK-0009: add policy-gated open_pr tool for agent-authored PRs`
- Основание: ADR-0011/ADR-0014, `AGENTS.md`.

## Статус реализации
- ✅ **Handler** `control-plane/src/sdlc/tools/vcs.py` (`OpenPRTool`, `register_vcs_tools`):
  branch/commit/push фиксированным argv (`shell=False`) + PR через GitHub REST; путь-confined
  в `--root`; branch по конвенции; deny protected-зон (`PROTECTED_PR_PATH`); секрет из
  `SDLC_GITHUB_TOKEN` (в контекст/evidence не попадает).
- ✅ **Регистрация** в `cli._cmd_mcp` (scope `vcs`) при наличии `SDLC_GITHUB_TOKEN`
  (иначе тулы нет — fail-closed).
- ✅ **Executor**: `resource` для OPA теперь берётся и из `args["paths"]` (join через `,`),
  не только `args["path"]`.
- ✅ **Тесты** `tests/test_vcs.py` (8): happy path, default title/base, bad branch, escape,
  absolute, protected zone, scope/resource через executor.
- ✅ Регресс: `ruff`, `mypy` (48 файлов), `pytest` **219 passed**.
- ⛔ **Политика** (`policies/pre_tool_call.rego`: гейт `PROTECTED_PR_PATH` для `open_pr`,
  тесты) — **защищённая зона, агент не правит**. Пока гейт на уровне OPA отсутствует, но
  handler сам отклоняет protected-пути, поэтому executor отвечает `EXECUTION_FAILED`
  (fail-closed). Требуется PR с CODEOWNERS, чтобы получить явный reason-код `PROTECTED_PR_PATH`.

## Критерии приёмки (acceptance)
1. Агент вызывает `open_pr` с `branch`, `commit_message`, `paths`, `base`, `title`, `body`.
2. Вызов идёт через `RunnerExecutor`: OPA `pre-tool-call` → scoped capability → schema args/result
   → handler; на каждый вызов `policy-decision` + `evidence-record`.
3. Затронутые пути, пересекающиеся с `protected_paths`, **deny** — сейчас на уровне handler
   (`EXECUTION_FAILED`), цель — явный `PROTECTED_PR_PATH` в OPA (protected zone).
4. Ветка только по конвенции `feature/{FEATURE-ID}-{TASK-ID}-slug`; commit message содержит task
   ID и ссылку на control/acceptance criterion.
5. Никаких произвольных флагов/команд: фиксированный argv, `shell=False`, без force-push/merge.
6. Секрет (GitHub token) живёт в окружении панели, не в model context и не в evidence.
7. Неизвестный tool / нет capability / policy недоступна → fail-closed; сбой handler'а → tool
   error, сервер (stdio-мост) жив.

## Контракт
`ToolSpec`: `name="open_pr"`, `scope="vcs"` (scope в rego не участвует — правка политики для
scope не нужна).

Args schema:
```json
{
  "type": "object",
  "required": ["branch", "commit_message", "paths"],
  "properties": {
    "branch": {"type": "string"},
    "commit_message": {"type": "string", "minLength": 1},
    "paths": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "base": {"type": "string"},
    "title": {"type": "string"},
    "body": {"type": "string"}
  },
  "additionalProperties": false
}
```
Result schema: `{"required": ["branch", "commit", "pr_url"]}`.

Инварианты handler'а (defence in depth, помимо OPA):
- каждый `path` — repo-relative, без `..`/абсолютных/выхода за `--root`;
- отказ, если список затрагивает `PROTECTED_PATH_MARKERS` (зеркало `protected_paths`);
- невалидная ветка → ValueError → `INVALID_TOOL_ARGS`/`EXECUTION_FAILED`;
- никакая пользовательская строка не подставляется на место флага.

## Реализация (сделано)
- `control-plane/src/sdlc/tools/vcs.py` — `register_vcs_tools(registry, root, *, git=None,
  open_pull_request=None)`; транспорт инъектируемый (тесты — без git/сети).
- Транспорт A: локальный `git` для ветки/коммита/пуша (фиксированный argv, `shell=False`,
  `cwd` в root) + GitHub REST `POST /repos/{owner}/{repo}/pulls` с токеном из `SDLC_GITHUB_TOKEN`
  и слагом из `SDLC_GITHUB_REPOSITORY`.
- `tools/__init__.py` — экспорт `OpenPRTool`, `register_vcs_tools`.
- `cli._cmd_mcp` — регистрация при наличии токена.
- `runner/executor.py` — `resource` из `args["paths"]`.

## Политика (protected zone — CODEOWNERS, TODO)
- `policies/pre_tool_call.rego`: расширить гейт на `open_pr` — deny `PROTECTED_PR_PATH`, если
  любой затрагиваемый путь попадает в `protected_paths` (сейчас `PROTECTED_PATH` смотрит только
  `write_file` и один `input.path`; для `open_pr` resource — paths через `,`).
- `policies/tests/pre_tool_call_test.rego`: кейсы (agent PR в `policies/` → deny; в `apps/` → allow).

## Модель угроз / контроли
- Угрозы: утечка токена в контекст, правка защищённой зоны, инъекция команд через аргументы,
  «тихая» правка чужого PR. Связать с TM-0001; добавить контроли (напр. `CTRL-0004`
  «capability-gated VCS», `CTRL-0005` «no protected-zone PR») через канонические artifacts.

## Не-цели / границы
- Нет merge, force-push, изменения protected branches, произвольного git.
- PR в защищённые зоны — только человек (агент получает deny).
- Контейнерная песочница VCS — вне среза (backlog roadmap).

## Риски / открытые вопросы
- Хранение токена: scoped GitHub App token vs PAT — нужно решение (ADR).
- `resource` при multi-path — сейчас join `,`; при росте числа путей — уточнить лимит.
- Идемпотентность: повторный `open_pr` для существующей ветки/PR — обновлять или ошибка.
- e2e против реального GitHub не прогонялся (нет токена/сети) — только unit с фейками.

## Definition of Done
- ✅ Критерии 1–2, 4–7 покрыты тестами; `ruff`/`mypy`/`pytest` зелёные.
- ⛔ Критерий 3 на уровне OPA + `opa test` — требует protected-zone PR (CODEOWNERS).
- Обновлены handoff/PR-план.
