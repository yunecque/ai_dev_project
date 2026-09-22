# ADR-0012: Solo-mode политика review при сохранении автоматических гейтов

- **Статус:** accepted (временно, до появления второго участника)
- **Дата:** 2026-09-22
- **Контекст:** Branch protection требовала 1 approving review и CODEOWNERS-review, но второй
  человек осознанно отложен в `docs/roadmap.md` (solo-mode MVP). Владелец не может approve свой
  код, а `enforce_admins=true` не допускает обхода. В результате ни один PR не мог быть влит, и
  M1 блокировался.
- **Решение:** в solo-mode на `main` выставить
  `required_approving_review_count = 0` и `require_code_owner_reviews = false`.
  **Сохраняются без изменений:** 15 required status checks, `strict` (branches up to date),
  `enforce_admins = true`, PR-only flow, запрет force-push и deletions, conversation resolution.
- **Обоснование:** автоматические гейты (схемы, тесты, SAST, secret-scan, policy-check,
  sbom/sign) — самая ценная и наименее подверженная влиянию часть контроля; их нельзя отключать.
  Human review подключается, как только появляется независимый ревьюер. Это конфигурационное
  отклонение solo-mode, **не** waiver на findings и не отмена обязательных security gates.
- **Условие возврата:** при появлении второго участника — вернуть 1 approval + CODEOWNERS
  (и перейти к 2 approvals, один из них security, согласно `docs/branch-protection.md`).
- **Последствия:** в solo-mode владелец (и агент с owner-токеном) может вливать PR без независимого
  human review; поэтому до возврата требования review нельзя считать действующим. Critical/High
  findings по-прежнему блокируют merge и deployment всегда.
- **Ссылки:** ADR-0008; `docs/branch-protection.md`; `docs/roadmap.md`.