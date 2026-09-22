# ADR-0010: Observability stack и обязательная redaction

- **Статус:** accepted
- **Дата:** 2026-09-21
- **Контекст:** Нужны traces/metrics/logs по golden path; при этом телеметрия не должна
  утекать секретами, токенами и PII.
- **Решение:** OpenTelemetry (traces/metrics/logs) → OTel Collector → Prometheus/Grafana
  (metrics), Loki (logs), Tempo (traces). Обязательная redaction секретов, токенов и PII
  перед экспортом.
- **Обоснование:** единый стандарт инструментирования, вендор-нейтральность, self-hosted.
- **Последствия:** redaction-процессор в Collector и тесты на отсутствие sensitive-полей
  в экспортируемой телеметрии.
- **Ссылки:** конституция §6; ADR-0003.
