# Staging stack (mini PC)

Stage-деплой платформы на mini PC (M4, TASK-0005). Полный стек: приложения из GHCR (подписанные
на `main`, TASK-0003/0004) + инфраструктура. Конфиги наблюдаемости переиспользуются из
`infra/compose/` (единый источник).

## Требования

- Linux (Ubuntu), Docker Engine + `docker compose` plugin.
- Образы приложений опубликованы в GHCR (`ghcr.io/<owner>/<repo>/{gateway,domain,publisher,worker}`).
- Приватные пакеты GHCR: `docker login ghcr.io` (например, через PAT с `read:packages`).

## Первый запуск

```bash
sudo mkdir -p /opt/secure-agentic-sdlc /etc/secure-agentic-sdlc
# скопировать репозиторий в /opt/secure-agentic-sdlc (git clone / rsync)
cd /opt/secure-agentic-sdlc

cp infra/staging/.env.example /etc/secure-agentic-sdlc/staging.env
# отредактировать /etc/secure-agentic-sdlc/staging.env: все CHANGE_ME, IMAGE_TAG (git sha)

ENV_FILE=/etc/secure-agentic-sdlc/staging.env bash infra/staging/deploy.sh
```

Проверка: `docker compose --env-file /etc/secure-agentic-sdlc/staging.env ps` — все сервисы `Up`
(`migrate` завершается с кодом 0).

## Автозапуск (systemd)

```bash
sudo cp infra/staging/systemd/secure-agentic-sdlc.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now secure-agentic-sdlc.service
```

`ExecStart` поднимает стек из `/opt/secure-agentic-sdlc/infra/staging` с env-файлом
`/etc/secure-agentic-sdlc/staging.env`; `ExecStop` останавливает.

## Обновление (release)

1. CI на `main` собирает, сканирует, подписывает и аттестует образы (TASK-0003/0004).
2. `deploy-verify` (`workflow_dispatch`) проверяет signature/SBOM/provenance и политику
   `pre-deployment` (TASK-0005 в M3, ADR-0013) независимо от сборки.
3. Выставить `IMAGE_TAG=<git-sha>` в env-файле и применить:
   `ENV_FILE=/etc/secure-agentic-sdlc/staging.env bash infra/staging/deploy.sh`.

## Порты

| Сервис | Порт | Назначение |
|---|---|---|
| Gateway | 8081 | REST API (`/healthz`, `/requests`) |
| Grafana | 3000 | dashboards |
| Prometheus | 9090 | metrics + alerts |
| Loki / Tempo | 3100 / 3200 | logs / traces |

Postgres, NATS, Keycloak, OPA, OTel Collector — только внутри compose-сети (наружу не публикуются).

## Безопасность

- Секреты — только в env-файле вне репозитория (`/etc/secure-agentic-sdlc/staging.env`), не в git.
- Телеметрия redacted в OTel Collector (ADR-0010); guard-тесты в control-plane.
- `staging` environment и проверки релиза — см. `docs/adr/0013-solo-mode-staging-environment.md`.
