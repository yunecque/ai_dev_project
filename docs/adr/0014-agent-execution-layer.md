# ADR-0014: Agent execution layer (runner-executor, MCP-мост, role skills, оркестратор)

- **Статус:** accepted (M6; вне MVP M0–M5)
- **Дата:** 2026-09-24
- **Контекст:** ADR-0011 зафиксировал необходимые слои границы контроля (`runner` + scoped token,
  MCP-медиация, `.opencode/` profiles), но они не были реализованы: MVP (M0–M5) умеет
  **проверять и фиксировать** (schemas, OPA-точки, evidence, waiver, traceability), однако не
  **исполняет** агентский конвейер. Канонические артефакты `idea → … → review` сейчас пишет
  человек/агент вручную. Нет: (1) runner-executor, (2) role skills, (3) MCP-моста,
  (4) pipeline-оркестратора. Без них «агент + платформа» не проходят контур автоматически.
- **Решение:**
  1. **Runner-executor как единственный исполнитель tool-вызовов.** Никакого произвольного shell:
     каждый вызов — именованный инструмент из allowlist с явным `scope` и JSON-схемой
     args/result. Исполнение происходит только после OPA `pre-tool-call` (fail-closed, ADR-0004)
     **и** проверки scoped capability (ADR-0011). Любая ошибка policy/капабилити/инструмента —
     deny.
  2. **Tool registry как контракт.** Инструменты (`read_artifact`, `write_artifact`, `run_tests`,
     `open_pr`, …) объявляются декларативно: имя, scope, схемы входа/выхода, роль исполнителя.
     Неизвестный инструмент — fail-closed deny (`UNKNOWN_TOOL`).
  3. **Role skills = trusted prompt + контракт артефакта.** Для каждой роли (из `actorRole`:
     `grill`, `grill-security`, `planner`, `task-writer`, `implementer`, `reviewer`) промпт —
     trusted config, а выход LLM — **untrusted data**, который проходит JSON Schema-валидацию и
     trust-pipeline (sensitive никогда не в контексте, ADR-0007). Инструкции из LLM-output не
     исполняются.
  4. **MCP-сервер — единственная дверь** для внешнего агента (`opencode`): экспозиция tools по
     MCP, аутентификация capability-токеном, каждый вызов проходит `pre-tool-call`.
  5. **Pipeline orchestrator** проводит вертикальный срез `idea → spec → threat → plan → task →
     implement → review`; на каждом шаге фиксируются `policy-decision` и `evidence-record`,
     артефакты валидируются по schema, финальная проверка — `sdlc trace` = COMPLETE.
  6. **Ограничение opencode** (`.opencode/`, защищённая зона): MCP-регистрация, урезанный
     `permission` (MCP как единственная дверь), plugin-хук `tool.execute.before`/`permission.ask`
     → OPA, role profiles.
  7. **Sandbox.** Начальный executor — in-process; это слабее контейнерной изоляции. Целевая
     песочница (ограничение syscalls/egress, эфемерный контейнер) — отдельный шаг; ограничение
     явно фиксируется в `docs/limitations.md`.
- **Обоснование:** контроль, спроектированный в ADR-0011, становится проверяемым только при
  наличии исполняющего слоя, который физически не имеет иного пути, кроме медиации через OPA и
  capability. Декларативный allowlist + schema-валидация + evidence на каждый вызов делают
  поведение агента аудируемым и воспроизводимым.
- **Последствия:**
  - новые защищённые пакеты `control-plane/src/sdlc/{tools,llm,skills,mcp,pipeline}/` и
    `.opencode/` (CODEOWNERS-ревью);
  - LLM-провайдер — сменная зависимость; для тестов обязателен детерминированный stub;
  - реальный внешний провайдер требует креденшелов — нельзя нарушать «нет долгоживущих
    секретов» (вариант — локальная модель или scoped ephemeral credential);
  - каждый tool-вызов обязан порождать `evidence-record`, каждый гейт — `policy-decision`.
- **Критерии приёмки (M6):** внешний агент только через MCP проводит срез `idea → task` с
  policy-гейтом на каждом вызове; артефакты schema-valid; `sdlc trace` = COMPLETE; sensitive вне
  контекста; агент не утверждает артефакты/релизы; неизвестный tool / нет capability /
  недоступная policy — fail-closed.
- **Ссылки:** ADR-0004; ADR-0007; ADR-0011; `docs/m6-agent-execution-layer.md`;
  `docs/roadmap.md`; `control-plane/src/sdlc/{policy,runner,evidence,trust}`.