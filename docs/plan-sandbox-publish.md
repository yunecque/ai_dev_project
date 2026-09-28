# План среза: песочница + публикация приложения в отдельный GitHub-репозиторий

Цель: агент пишет новое приложение в **песочнице** внутри workspace панели; песочница
**никогда не попадает в публичный репозиторий панели**; по команде агент **публикует**
приложение в отдельный (по умолчанию приватный) GitHub-репозиторий через policy-gated
панельную тулу.

- Feature: `FEAT-0006` (agent execution layer), Task: `TASK-0010`
- Ветка: `feature/FEAT-0006-TASK-0010-sandbox-publish-app`
- Commit: `FEAT-0006/TASK-0010: add sandbox isolation and publish_app tool`
- Связанное: `docs/plan-open-pr-tool.md` (там же базовая тула `open_pr` и транспорт git/REST).

## Модель (что где)
- **Панель / публичный репо** — `yunecque/ai_dev_project`: control plane, политики, guardrails.
  Публичный. Туда песочница не должна попадать никогда.
- **Песочница** — `<panel-root>/sandbox/<name>/`, каталог в workspace панели, добавленный в
  `.gitignore`. Прототип приложения.
- **Продукт** — отдельный репозиторий `owner/<name>` (private по умолчанию): код сервиса +
  CI/Dockerfile для сборки образа + деплой.

## Критерии приёмки (acceptance)
1. Каталог песочницы (`sandbox/`) **не трекается** панельным репо: есть правило в
   `.gitignore`; guard-тест проверяет, что `git ls-files` не содержит `sandbox/`.
2. `open_pr`/`git` в панельном репо **не могут** опубликовать пути песочницы (OPA-правило
   `SANDBOX_PR_DENY` + проверка в handler'е).
3. Новая тула `publish_app`: берёт исходники **только** из `sandbox/<name>/`, path-confined,
   никогда не читает protected/sensitive-зоны.
4. `publish_app` создаёт репозиторий (если нет) и публикует файлы; **visibility = private по
   умолчанию**; публичный требует явного `private: false` и отдельного allow-правила.
5. Секрет (`SDLC_GITHUB_TOKEN`) живёт только в окружении панели; в model context/evidence не
   попадает. Токен для push/API не персистится в `.git/config` (не пишем токен в remote URL).
6. Каждый вызов проходит OPA `pre-tool-call` → scoped capability → schema args/result →
   handler; пишется `policy-decision` + `evidence-record`.
7. Любая ошибка/неизвестный tool/нет capability/нет токена → fail-closed; сбой handler'а → tool
   error, stdio-мост жив.
8. Повторная публикация поверх существующего непустого репо/ветки → отказ (без force-push).

## Изоляция песочницы (чтобы не утекла в публичный репо)
- `.gitignore` панели: добавить
  ```
  # --- Agent sandbox (never published with the panel) ---
  /sandbox/
  ```
  (`.gitignore` — не protected-зона, правится обычным срезом.)
- Политика (`policies/pre_tool_call.rego`, protected zone): правило `SANDBOX_PR_DENY` —
  deny `open_pr`/`write_file`-в-панельный-репо, если путь начинается с `sandbox/`.
- Guard-тест в `control-plane/tests/`: `.gitignore` содержит `/sandbox/` и `sandbox/` не в
  `git ls-files` (или не отслеживается через `git check-ignore`).
- Handler `publish_app` hard-refuse: `source` не под `sandbox/` → ValueError.

## Контракт
`ToolSpec`: `name="publish_app"`, `scope="vcs"` (тот же scope, что `open_pr`).

Args schema:
```json
{
  "type": "object",
  "required": ["source", "repo", "commit_message"],
  "properties": {
    "source": {"type": "string"},
    "repo": {"type": "string"},
    "private": {"type": "boolean"},
    "branch": {"type": "string"},
    "commit_message": {"type": "string", "minLength": 1},
    "title": {"type": "string"},
    "body": {"type": "string"}
  },
  "additionalProperties": false
}
```
Result schema: `{"required": ["repo", "url", "branch", "commit"]}`.

Инварианты handler'а:
- `source` — repo-relative, начинается с `sandbox/`, без `..`/абсолютных/выхода за root;
- `repo` — `owner/name` (regex); visibility по умолчанию `private: true`;
- не читаются protected/sensitive-маркеры (зеркало списка политики — defence in depth);
- лимит числа файлов/размера; бинарные/большие файлы — по решению (см. вопросы).

## Реализация (эскиз)
- `control-plane/src/sdlc/tools/publish.py` (новый): `PublishAppTool`,
  `register_publish_tools(registry, root, *, git=None, api=None)`; транспорт инъектируемый
  (тесты — без git/сети).
- Транспорт:
  - **создание репо**: GitHub REST `POST /user/repos` (или `/orgs/{org}/repos`) с
    `{"name","private":true,...}`;
  - **публикация кода**: локальный `git init` **внутри** `sandbox/<name>/` (родитель его
    игнорирует), `git add -- <files>`, `git commit`, `git branch -M <branch>`,
    `git remote add origin …`, `git push` — фиксированный argv, `shell=False`, `cwd` = sandbox;
    push — через настроенный на хосте credential manager (как в `open_pr`), токен в URL не
    пишем. Альтернатива: GitHub Git Data API (blobs/tree/commit/ref) без git-бинаря — рассмотреть
    при ревью (см. вопросы).
  - опционально: PR в новом репо для последующих изменений (переиспользовать логику `open_pr`).
- `tools/__init__.py` — экспорт; `cli._cmd_mcp` — регистрация при наличии
  `SDLC_GITHUB_TOKEN` (иначе тулы нет).
- `runner/executor.py` — `resource` из `args["source"]` (добавить к выводу из `path`/`paths`).
- Guard-тест песочницы в `control-plane/tests/test_sandbox.py`.

## Политика (protected zone — CODEOWNERS)
- `policies/pre_tool_call.rego`: добавить `publish_app` в `allowed_tools`; правила
  `SANDBOX_PR_DENY` (не публиковать песочницу в панельный репо) и `PRIVATE_REPO_REQUIRED`
  (публичный repo — только явным allow). Для `publish_app` resource — `source`.
- `policies/tests/pre_tool_call_test.rego`: кейсы (source вне sandbox → deny; public без
  разрешения → deny; sandbox→панельный open_pr → deny; happy path → allow).

## Модель угроз / контроли
- Угрозы: утечка кода песочницы в публичный репо панели; утечка токена; публикация в public
  по ошибке; чтение protected/sensitive при публикации; инъекция команд через `repo`/`source`.
- Контроли: `.gitignore` + `SANDBOX_PR_DENY` (CTRL: sandbox never published with panel);
  private-by-default; path confinement; фиксированный argv/`shell=False`; токен только в env;
  evidence на каждый вызов. Связать с TM-0001; при необходимости добавить `CTRL-0006`
  «sandbox isolation», `CTRL-0007` «private-by-default publish» через канонические artifacts.

## Тест-план (risk-based TDD: сначала failing tests)
- `tests/test_sandbox.py`:
  - `.gitignore` содержит `/sandbox/`; `sandbox/` не отслеживается;
  - guard: `open_pr` с sandbox-путём → deny.
- `tests/test_publish.py` (фейки git/api):
  - happy: source=`sandbox/app/`, private по умолчанию, repo создаётся, push, результат
    schema-valid;
  - `source` вне sandbox / `..` / абсолютный → ValueError, без git/сети;
  - `source` содержит protected-маркер → отказ;
  - `private: false` без разрешения → отказ;
  - существующий непустой repo/ветка → отказ (без force);
  - секрет не попадает в evidence.
- `tests/test_executor.py`: `publish_app` проходит capability-гейт; `scope` mismatch → deny.
- `opa test policies/` — новые кейсы.
- Регресс: `ruff`, `mypy`, `pytest`.

## Не-цели / границы
- Нет удаления/transfer/смены видимости существующих repo; нет force-push; нет merge.
- Публичные репозитории — не по умолчанию (только явный allow-политикой).
- Песочница — не рантайм; продукт = отдельный repo + образ + деплой.
- Вынос с историей из панельного репо (`filter-repo`) — вне среза.

## Открытые вопросы
- Scope токена: создание репо требует `administration`/`repo` — шире, чем для PR. Нужен ADR и,
  по возможности, GitHub App с точечными permission'ами + scoped installation token.
- Транспорт публикации: локальный git + credential manager vs GitHub Git Data API (последний
  не персистит токен и не требует git-бинаря — предпочтительнее для новых репо).
- Поддержка бинарников/больших файлов (Git LFS?) — пока нет.
- Именование/владелец: личный аккаунт или org; шаблон репозитория (лицензия, CI, branch
  protection) при создании.
- Автосоздание репо vs требовать созданный заранее (по умолчанию — авто, private).

## Definition of Done
- Критерии 1–8 покрыты тестами; `ruff`/`mypy`/`pytest` зелёные; `opa test` зелёный (после
  protected-правки).
- Песочница не отслеживается панельным репо; guard-тест это подтверждает.
- Evidence на каждый вызов; секретов в контексте/evidence нет.
- Обновлены handoff/PR-план; protected-часть — через CODEOWNERS-PR.
