# WSL toolchain

User-local toolchain bootstrap (no `sudo`). Installs baseline v1 tooling into `~/.local`
and `~/.local/go`, resolves versions into `toolchain.lock`, and fixes `PATH`.

## Использование

```bash
# внутри WSL Ubuntu
bash /mnt/c/Users/zarl3/IdeaProjects/ai_dev_project/infra/wsl/bootstrap-toolchain.sh
source ~/.profile          # подхватить PATH
bash .../bootstrap-toolchain.sh --check    # только отчёт
bash .../bootstrap-toolchain.sh --latest   # пере-резолвить свежие версии
```

## Что ставится

| Инструмент | Назначение | Источник |
|---|---|---|
| go | production-сервисы | go.dev |
| opa | policy engine | GitHub releases (raw) |
| gh | GitHub control plane | GitHub releases |
| cosign | keyless signing | GitHub releases (raw) |
| syft | SBOM | GitHub releases |
| trivy | dependency + container scan | GitHub releases |
| gitleaks | secret scan | GitHub releases |
| buf | Protobuf tooling | GitHub releases (raw) |
| semgrep | SAST | uv tool |
| uv | Python tool runner | astral.sh |

`toolchain.lock` фиксирует установленные версии (governance: воспроизводимость).

## Требует `sudo` (пока не сделано)

Ничего критичного: всё выше ставится user-local. Если понадобится системный пакет
(например, `python3-venv`), выполните вручную:

```bash
sudo apt update && sudo apt install -y python3-venv
```

## Docker

Docker Desktop установлен на Windows и интегрирован в WSL (`/usr/bin/docker`).
Локальный стек: `infra/compose/`.
