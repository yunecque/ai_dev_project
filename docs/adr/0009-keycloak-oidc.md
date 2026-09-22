# ADR-0009: Keycloak / OIDC и scoped service identities

- **Статус:** accepted
- **Дата:** 2026-09-21
- **Контекст:** Нужна аутентификация пользователя и передача verified identity context между
  сервисами; у каждого компонента должна быть минимальная привилегия.
- **Решение:** OIDC через Keycloak. Отдельные scoped service identities для gateway,
  domain-service, broker publish/subscribe и CI/deployment workload. Gateway валидирует JWT и
  передаёт verified identity context по gRPC.
- **Обоснование:** стандартный протокол, self-hosted, разделение привилегий по компонентам.
- **Последствия:** требуется realm-конфигурация и ротация клиентов; downstream не доверяет
  клиентским claims, а полагается на context, проверенный gateway.
- **Ссылки:** конституция §6.
