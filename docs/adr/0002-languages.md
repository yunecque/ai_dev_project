# ADR-0002: Go для production-сервисов, Python для control plane, Rego для policy

- **Статус:** accepted
- **Дата:** 2026-09-21
- **Контекст:** Нужны конкурентные сетевые сервисы с gRPC и обработкой сообщений; агентная
  автоматизация с богатой LLM/экосистемой; декларативные policy-решения.
- **Решение:**
  - Go — production-сервисы (gateway, domain, worker), gRPC, NATS consumers.
  - Python 3.12 — agent/control plane, orchestration, automation.
  - Rego/OPA — policy-as-code.
- **Обоснование:** Go даёт статическую типизацию, малый runtime и хорошую gRPC/конкурентность.
  Python ускоряет разработку агентной части и интеграцию с LLM. Rego — стандарт OPA.
- **Последствия:** два toolchain'а и два набора CI-стадий; общий контракт — Protobuf/OpenAPI,
  а не shared library.
- **Ссылки:** конституция §6; ADR-0004.
