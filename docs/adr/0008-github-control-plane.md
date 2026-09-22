# ADR-0008: GitHub как control plane MVP

- **Статус:** accepted
- **Дата:** 2026-09-21
- **Контекст:** Нужны issue-driven старт, review-контейнер, CI-гейты, evidence, separation of
  duties и OIDC для keyless signing без собственного control plane UI.
- **Решение:** GitHub — control plane MVP. Issue инициирует feature; PR — контейнер
  review/CI/evidence; CODEOWNERS + branch protection реализуют separation of duties; Actions
  выполняет только детерминированные проверки и не хранит постоянный LLM API key.
- **Обоснование:** минимальные затраты, нативные OIDC/attestations, прозрачный audit trail.
- **Последствия:** зависимость от GitHub; собственный web UI control plane отложен в roadmap.
- **Ссылки:** конституция §7, §9; ADR-0005.
