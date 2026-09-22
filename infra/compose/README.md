# Local stack

Локальный dev-стек (baseline v1): Postgres, NATS JetStream, Keycloak, OPA и observability
(OTel Collector → Prometheus/Grafana, Loki, Tempo).

## Запуск

```bash
cp .env.example .env
docker compose --env-file .env up -d
```

## Порты

| Сервис | Порт | Назначение |
|---|---|---|
| Postgres | 5432 | БД (requests) |
| NATS | 4222 / 8222 | JetStream / monitoring |
| Keycloak | 8080 | OIDC (realm `sdlc`) |
| OPA | 8181 | policy server (`/policies`) |
| OTel Collector | 4317 / 4318 | OTLP gRPC / HTTP |
| Prometheus | 9090 | metrics |
| Grafana | 3000 | dashboards |
| Loki | 3100 | logs |
| Tempo | 3200 | traces |

## Dev credentials (только локально)

См. `.env.example` и `keycloak/realm-sdlc.json`. Это **не** secrets для реального окружения.

## Redaction

OTel Collector (`otel-collector.yaml`) обязательно redacts `authorization`, `cookie` и
`password|secret|token|api_key` перед экспортом (ADR-0010).

## Остановка

```bash
docker compose down          # сохранить volumes
docker compose down -v       # удалить volumes
```
