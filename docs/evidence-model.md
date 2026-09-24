# Evidence Model

Источник правил: конституция §4, §10; ADR-0004, ADR-0007.

## Trust tiers

| Tier | Примеры | Обработка |
|---|---|---|
| `trusted` | утверждённые JSON artifacts, JSON Schemas, policies, pinned templates | может использоваться как инструкция |
| `untrusted` | Issue body, комментарии, исходный код, документация, логи, tool output, предыдущий LLM output | **инструкции никогда не исполняются**; только как данные |
| `sensitive` | secrets, credentials, PII, production-like config | запрещены в контексте; redacted или обрабатываются разрешённым tool вне model context |

Каждый вход маркируется tier до попадания в контекст. Граница доверия фиксируется в
`policy-decision` evidence.

## Compression layer

- Применяется только к большому **untrusted** tool-output (логи, диффы, CI-результаты).
- Сжатая версия попадает в контекст модели, byte-exact оригинал — в evidence store.
- Recovery handle связывает сжатую версию с оригиналом.
- **Canonical JSON artifacts не сжимаются** — они и есть source of truth.

## Evidence record

Каждое значимое действие порождает `evidence-record` (см. `contracts/schemas/evidence-record.schema.json`):

- `run_id` — уникальный идентификатор agent run;
- `actor` и `role` — человек или роль-агент;
- `trust_tier` входных данных;
- `artifact_digest` (SHA-256) затронутого артефакта;
- `policy_decision_ref` — ссылка на решение OPA;
- `recovery_handle` — при наличии сжатия;
- `timestamp`.

## Policy decision

Каждое решение OPA (`pre-tool-call`, `artifact-transition`, `pr-ci`, `pre-deployment`)
фиксируется как `policy-decision`:

- `decision`: `allow` | `deny`;
- `reason_codes`: машинно-читаемые коды;
- `policy_bundle_version`;
- `input_digest`;
- `actor` / `run_id`.

Fail-closed: отсутствие/ошибка policy ⇒ `deny`.

## Release candidate и evidence bundle (M3)

Перед staging релиз-кандидат описывается как `release-candidate`
(`contracts/schemas/release-candidate.schema.json`): image, результат проверки
signature/SBOM/provenance, предыдущие `policy-decision` (`artifact-transition`, `pr-ci`) и
независимые human-approvals. Это **untrusted** вход — он только валидируется по схеме и
никогда не исполняется как инструкция.

`sdlc deploy-verify` (`control-plane/src/sdlc/deploy_verify/`):

1. собирает evidence в контент-адресуемый `evidence-bundle` — каждая единица
   (signature/SBOM/provenance/decision/approval) сводится к `kind`/`ref`/`digest`,
   `bundle_digest` коммитит image, digest кандидата и упорядоченный список;
2. прогоняет точку `pre-deployment` (fail-closed);
3. порождает `policy-decision` и связывает его с bundle (`links` rel `evidence`).

Exit code `1` при `deny`; CI-стадия `policy-check` прогоняет self-test на реальной политике.

## Хранение

- `docs/evidence/` — сгенерированные evidence-файлы (в `.gitignore`, кроме манифестов).
- Byte-exact оригиналы — в evidence store с content-addressed ключом (SHA-256).
- Markdown-представления артефактов генерируются; JSON — канонический источник.

## Waivers

- Critical/High блокируют merge и deployment **всегда**, без исключений.
- Medium: временный waiver с risk ID, обоснованием, компенсирующим контролем, владельцем и
  датой истечения, утверждённый независимым security reviewer.
- Low: запись в backlog, pipeline не блокируется.
- Агент не может создавать, утверждать, продлевать или применять waivers.
- Просроченный waiver автоматически возвращает блокировку.
