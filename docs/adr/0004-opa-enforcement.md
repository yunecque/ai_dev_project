# ADR-0004: OPA fail-closed в четырёх обязательных точках

- **Статус:** accepted
- **Дата:** 2026-09-21
- **Контекст:** Агент и LLM недоверенны; нужны единообразные, проверяемые и версионируемые
  решения о разрешении действий, которые нельзя отключить из application-кода.
- **Решение:** Open Policy Agent (Rego) как единственный policy engine. Обязательные,
  fail-closed точки: `pre-tool-call`, `artifact-transition`, `pr-ci`, `pre-deployment`.
  Решения — machine-readable allow/deny с reason codes, версией bundle, input digest,
  actor/run ID; сохраняются как evidence.
- **Обоснование:** policy вынесена из кода, под CODEOWNERS, воспроизводима и аудируема.
  Fail-closed гарантирует, что отсутствие/сбой policy не приводит к разрешению.
- **Последствия:** каждый enforcement point должен иметь OPA-клиент и digest входных данных;
  нельзя кэшировать разрешения дольше версии bundle.
- **Ссылки:** конституция §10; ADR-0008.
