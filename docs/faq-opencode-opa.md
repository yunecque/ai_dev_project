# FAQ: opencode ↔ OPA `pre-tool-call` (разбор инцидента)

Кейс: агент opencode перестал вызывать любые инструменты; каждый tool-call отклонялся. Ниже —
что это было, как диагностировать и как чинить. Чтобы в следующий раз не копать заново.

## Симптомы (в порядке появления)

1. `OPA denied tool read: POLICY_UNAVAILABLE` — буквально все тулзы.
2. После поднятия OPA: `OPA denied tool read: TOOL_NOT_IN_ALLOWLIST`.
3. В логах контейнера OPA: `41 errors occurred during loading`, затем процесс завершается.

## Архитектура (кто на каком слое)

| Слой | Что | Роль |
|---|---|---|
| Windows-хост / IDE | `opencode` + `plugin/opa-guard.ts` | PEP — перехватывает каждый tool-call |
| Docker-контейнер `opa` | `policies/*.rego`, `opa run --server :8181` | PDP — принимает решение allow/deny |
| `control-plane` | `sdlc mcp`, runner, executor | MCP «единственная дверь» (опционально) |

Плагин никогда не в контейнере — он там, где запущен opencode (Windows). Контейнер только
отвечает на `POST /v1/data/sdlc/pre_tool_call/decision`.

## Причина №1: контейнер OPA падал при старте

`opa run` при ошибке компиляции bundle **выходит**. Отсюда `connection refused` и
`POLICY_UNAVAILABLE` (плагин fail-closed). Причины ошибок загрузки:

- политики в Rego v0 (`some x in xs` без `import future.keywords.in`);
- тесты (`policies/tests/*_test.rego`) написаны в Rego v1 (`rule if {}`) и не грузятся вместе
  с рантайм-политиками.

**Фикс:** серверу не нужны тесты; в рантайм-файлы — импорт ключевых слов.

```powershell
# рантайм-файлы: после `package ...` добавить
#   import future.keywords.in
# и грузить без каталога tests
docker run -d --name opa -p 8181:8181 `
  -v "C:\Users\zarl3\IdeaProjects\ai_dev_project\policies:/policies:ro" `
  openpolicyagent/opa:latest run --server --addr 0.0.0.0:8181 /policies
```

Проверка: `curl.exe http://localhost:8181/v1/data` возвращает непустой JSON (не `{}`).

> Замечание: `opa run` **не** перечитывает `.rego` на лету. После правок политики — рестарт
> контейнера (`docker rm -f opa` + заново), иначе работает старая версия.

## Причина №2: имена тулз не совпадают со словарём политики

Плагин отправлял **нативное** имя opencode (`read`, `glob`), а `allowed_tools` в
`policies/pre_tool_call.rego` содержит другой словарь (`read_file`, `write_file`, `list_files`,
`skill.<name>`, …). Пересечения нет → `TOOL_NOT_IN_ALLOWLIST`.

**Фикс:** маппинг в плагине (`toPolicyTool`):

```ts
read            -> read_file
write | edit    -> write_file
glob | grep     -> list_files
skill           -> skill.<args.name>
# всё остальное -> как есть (остаётся denied)
```

Не маппить `bash` на `run_tests` — это расширило бы права до произвольных команд.
`task`, `todowrite`, `webfetch`, `websearch`, `question` в словаре отсутствуют и остаются
запрещёнными (для них — command-policy отдельным PR).

## Причина №3: Windows-пути не ловят слэш-маркеры

`SENSITIVE_PATH` проверяет `contains(input.path, marker)`. Маркеры `"secrets/"` и
`"credentials/"` используют прямой слэш, а Windows-путь — обратный (`secrets\`), поэтому эти
два маркера не срабатывают. `.env`, `.pem`, `.key`, `id_rsa` работают всегда.

**Фикс:** нормализовать путь в плагине:
```ts
.replace(/\\/g, "/")
```

## Причина №4: защищённые зоны не были защищены

`write_file` разрешался **везде**, включая `policies/`, `.github/`, `contracts/`, `.opencode/`
— защищённые зоны по AGENTS.md. Добавлено правило `PROTECTED_PATH`: прямой `write_file` в
защищённые пути запрещён; для `specs/` — только через `write_artifact`.

## Причина №5: stdio-мост в кодировке локали (cp1251) + падение на плохом запросе

Симптом: панельный `write_file` рвёт MCP на теле >~4 КБ (`Connection closed`), а не-ASCII
документы сохраняются кракозябрами (`Р°РіРµРЅС‚СЃРєРёР№` вместо «агентский»).

Причина: `cli._cmd_mcp` читал/писал stdio в текстовом режиме с кодировкой **локали Windows**
(cp1251), а не UTF-8. UTF-8-тело декодировалось как cp1251 (двойная перекодировка при записи
документа), а при неудачной перекодировке/обрыве пайпа `UnicodeError`/`BrokenPipeError`
выходил из `for line in sys.stdin` — процесс завершался, opencode видел `Connection closed`
при живом транспорте.

**Фикс:** `cli.serve_stdio`:
- `_force_utf8` переводит stdin/stdout в UTF-8 (`errors="replace"`); для StringIO — no-op;
- обработка каждой строки в `try/except`: сбой запроса → JSON-RPC `INTERNAL_ERROR`
  (fail-closed), сервер продолжает работать.

Проверка: `pytest tests/test_stdio.py`; затем e2e `write_file` с кириллицей >4 КБ — файл на
диске байт-в-байт UTF-8. Регрессия-артефакты этой ошибки — `docs/runbook-agent-stack.md` и
`docs/pr-plan-opencode-opa.md` (перезаписаны корректным UTF-8).

## Нюанс: `permission.edit=deny` и MCP

`.opencode/opencode.json` задаёт `permission.edit=deny`, `bash=deny`, `webfetch/websearch=deny`.
Это IDE-уровень, срабатывает **раньше** плагина: после перезапуска агент не может напрямую
править файлы и запускать команды. Изменения — только через MCP `sdlc-platform`
(`write_artifact`/`open_pr`/`run_tests`). Если MCP не поднят — агент фактически read-only.

## Панельный пишущий режим (write_file через MCP)

Чтобы агент менял функциональный код, не открывая прямой доступ, добавлен allowlisted tool
`write_file`, исполняемый **панелью** (слои не смешиваются):

- хост-слой остаётся `permission.edit=deny` (прямые правки запрещены);
- агент зовёт MCP-тулзу `write_file`; плагин пропускает `sdlc_*`;
- панель (`sdlc mcp`) исполняет через `RunnerExecutor`: OPA `pre-tool-call` → capability →
  scope → схема args/result → handler;
- путь уходит в политику как `resource`, поэтому `SENSITIVE_PATH` и `PROTECTED_PATH`
  работают для MCP-вызовов (ранее `resource` был пуст — путь не проверялся);
- `WorkspaceWriter` дополнительно удерживает запись внутри `--root` (без `..`/абсолютных путей).

Capability не нужна агенту: stdio-мост — доверенный код, он минтит scoped-токен на каждый
`tools/call` (`inject_capability`). Секрет не персистится: без `SDLC_MCP_SECRET` берётся
per-process случайный (мост — единственный issuer и verifier).

Запуск локально:
```bash
# из control-plane/, с активированным venv и поднятым OPA
sdlc mcp --root /path/to/repo
```
В `.opencode/opencode.json` MCP уже зарегистрирован (`command: ["sdlc","mcp"]`). Убедитесь, что
`sdlc` доступен в PATH того окружения, где opencode стартует MCP.

Ограничения:
- это **in-process** запись на хосте, не контейнерная песочница (см. `docs/limitations.md`);
- агенту следует слать **repo-относительные** пути; абсолютный путь будет отвергнут;
- `open_pr` пока не реализован — это следующий шаг (PR-путь каноничнее).

## Панельный `run_tests` (режим B: агент сам прогоняет проверки)

Чтобы агент запускал проверки без `bash`, добавлен allowlisted tool `run_tests`
(`tools/commands.py`):

- агенту передаётся **явный argv**, не shell-строка; `shell=False`, cwd внутри `--root`
  (по умолчанию корень; можно указать подпапку, напр. `control-plane`), таймаут, обрезка вывода
  до 20k символов;
- `argv[0]` — только «голое» имя из allowlist: `ruff`, `mypy`, `pytest`, `opa`, `gofmt`, `go`
  (пути и `..` в имени программы запрещены);
- как и все панельные тулзы, вызов проходит OPA `pre-tool-call` и фиксируется в evidence.

Примеры вызовов (MCP): `{"argv": ["pytest", "-q"]}`, `{"argv": ["ruff", "check", "src", "tests"]}`,
`{"argv": ["opa", "test", "policies/"]}`.

Важно: запуск тестов = исполнение кода репозитория (по определению), поэтому это
capability-исполнение, а не песочница; вывод уходит в контекст модели — не печатайте секреты.
Активация: MCP `sdlc mcp` должен быть запущен в окружении с тулчейном (venv + `opa`), и
opencode перезапущен — тогда появляется `run_tests`.


## Чек-лист проверки (после любого фикса)

```powershell
docker ps                 # opa Up, порт 8181 опубликован
docker logs opa           # НЕТ "errors occurred during loading"
curl.exe http://localhost:8181/v1/data   # непустой JSON
```

Затем в opencode:
- позитив: `read` обычного файла → allow;
- негатив: `read` пути с `.env`/`.key` → deny `SENSITIVE_PATH`;
- защищённая зона: `write` в `policies/…` → deny `PROTECTED_PATH`.

## Частые грабли

- Правки плагина **не** применяются без полного перезапуска opencode.
- `--ignore 'tests/**'` не матчит `/policies/tests/...`; надёжнее не монтировать тесты или
  `--ignore "/policies/tests/*"`, либо `import rego.v1` во всех файлах.
- `/health` у OPA зелёный даже при невалидном/пустом bundle — не ориентируйтесь на него.
- `sdlc_*` тулзы плагин пропускает (медиация на стороне платформы), нативный `read` — нет.
- Смешали слои? Проверьте, где живёт агент: на хосте URL `localhost:8181`, в контейнере — имя
  сервиса (`http://opa:8181`), не `localhost`.

## Карта файлов

| Файл | Зачем |
|---|---|
| `.opencode/plugin/opa-guard.ts` | PEP: маппинг имён + `\`→`/` + вызов OPA |
| `.opencode/opencode.json` | MCP-регистрация, `permission`, регистрация плагина |
| `policies/pre_tool_call.rego` | allowlist, sensitive-маркеры, protected-пути |
| `policies/tests/pre_tool_call_test.rego` | тесты политики (`opa test`) |
| `.opencode/README.md` | раздел «Что может сломаться» |
