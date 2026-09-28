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

## Что может сломаться (прочитать до отладки)

- **`permission.edit=deny` + `bash=deny` → агент read-only.** После перезапуска opencode
  прямой `write`/`edit`/`bash` блокируется самой IDE, *до* плагина. Правки и проверки должны
  идти через MCP `sdlc-platform` (`write_artifact`/`open_pr`/`run_tests`). Если MCP не запущен
  (`sdlc mcp` не в PATH, нет capability-секрета), агент ничего не изменит — это by design, не баг.
- **Плагин грузится один раз.** Правки `plugin/opa-guard.ts` не подхватываются «на лету»; нужен
  полный перезапуск opencode, иначе работают старые правила.
- **OPA недоступен → всё запрещено.** Плагин fail-closed: если контейнер OPA не слушает
  `localhost:8181` (упал/не стартовал), каждый tool-call получает `POLICY_UNAVAILABLE` и deny.
- **OPA не перечитывает политики.** Сервер запущен с `opa run ... /policies` без `--watch`;
  после правок `.rego` нужен рестарт контейнера, иначе действует старая версия политики.
- **Windows-слэши.** Маркеры `secrets/` и `credentials/` в политике используют прямой слэш.
  Плагин нормализует путь (`\` → `/`), но **другие** вызовы (control-plane, MCP) могут слать
  сырой Windows-путь, и тогда эти два маркера не сработают. Слэш-независимые маркеры
  (`.env`, `.pem`, `.key`, `id_rsa`) работают всегда.
- **`protected_paths` в политике.** Прямой `write_file` в `policies/`, `.github/`,
  `contracts/`, `security/`, `infra/`, `specs/`, `.opencode/`, `docs/adr/`, `docs/roadmap.md`,
  `baseline.json`, `ARCHITECTURE_BASELINE.md` запрещён. Для `specs/` используйте
  `write_artifact`. Локальные правки защищённых файлов делайте внешним редактором, не агентом.
- **Маппинг имён.** `toPolicyTool` переводит нативные тулзы opencode в словарь политики
  (`read→read_file`, `write`/`edit`→`write_file`, `glob`/`grep`→`list_files`,
  `skill→skill.<name>`). Тулзы без маппинга (`bash`, `task`, `todowrite`, `webfetch`,
  `websearch`, `question`) всегда denied. При добавлении новых тулз обновите и плагин, и
  `allowed_tools` в политике — иначе они будут молча запрещены.
- **`skill.<name>`.** Имя берётся из `args.name`; если opencode положит его в другое поле,
  получится `skill.` → deny.
