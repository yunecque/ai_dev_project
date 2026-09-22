# ADR-0007: Trust-tier модель входных данных и compression layer

- **Статус:** accepted
- **Дата:** 2026-09-21
- **Контекст:** Issue body, код, логи, tool output и предыдущий LLM output недоверенны и могут
  содержать prompt injection. Большой untrusted output переполняет контекст модели.
- **Решение:** три trust-tier: `trusted` (утверждённые JSON artifacts, schemas, policies, pinned
  templates), `untrusted` (Issue, комментарии, код, документация, логи, tool output, LLM output),
  `sensitive` (secrets, credentials, PII, production-like config). Инструкции внутри
  untrusted-контента никогда не исполняются как команды.
  Большой untrusted tool-output проходит compression layer: сжатая версия — в контекст,
  byte-exact оригинал — в evidence store с recovery handle. Canonical JSON artifacts не сжимаются.
- **Обоснование:** явная граница доверия + byte-exact evidence сохраняют аудируемость при
  ограниченном контексте.
- **Последствия:** каждый вход маркируется tier; sensitive redacted или обрабатывается только
  разрешённым tool без попадания в model context.
- **Ссылки:** конституция §4; docs/evidence-model.md.
