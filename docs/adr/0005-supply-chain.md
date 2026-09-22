# ADR-0005: SBOM, Cosign keyless и provenance

- **Статус:** accepted
- **Дата:** 2026-09-21
- **Контекст:** Релизный артефакт должен иметь проверяемую цепочку поставки; долгоживущие
  signing-ключи в CI недопустимы.
- **Решение:** Syft генерирует SBOM; Cosign подписывает образ keyless через GitHub OIDC;
  GitHub artifact attestations формируют provenance. `deploy-verify` проверяет
  signature/SBOM/provenance/policy/approvals независимо от build job. Стадии сборки/подписи
  запускаются только из protected branch на смерженном коммите.
- **Обоснование:** keyless устраняет хранение приватных ключей; независимая проверка отделяет
  build от release-решения.
- **Последствия:** требуется публичный/подходящий repo с OIDC и environment с required reviewer.
- **Ссылки:** конституция §3, §9; ADR-0008.
