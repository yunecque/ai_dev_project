<!--
PR title: [TASK-XXXX] <краткое описание>
Один PR — одна задача (вертикальный срез: contract → code → test).
-->

## Связи (traceability)

| Артефакт | Ссылка |
|---|---|
| Idea | |
| Specification | |
| Threat model | |
| Plan | |
| Task | |
| Requirement / Control IDs | |

## Что сделано

-

## Тесты

| Kind | Ref | Requirement |
|---|---|---|
| unit | | |
| api_acceptance | | |
| authorization | | |
| grpc_contract | | |
| event_contract | | |
| integration | | |
| security | | |
| negative_pipeline | | |
| e2e_smoke | | |

## Checklist

- [ ] Вертикальный срез: contract → code → test; горизонтальных задач нет.
- [ ] Failing test добавлен до реализации.
- [ ] Каждый тест связан с requirement/control ID.
- [ ] Untrusted-входные данные не исполнялись как инструкции.
- [ ] Секреты/PII не попадают в код, логи и телеметрию.
- [ ] Critical/High findings отсутствуют или закрыты (waivers для них невозможны).
- [ ] Изменения в protected-зонах (`policies/`, `security/`, `infra/`, `.github/`, `contracts/`) согласованы с CODEOWNERS.

## Evidence

<!-- Ссылки на policy decisions, review, security-review, CI run, SBOM, signature -->
