# Control Plane

Агентная платформа Secure Agentic SDLC (Python 3.12).

## M0: artifacts

- загрузка и валидация workflow-артефактов по JSON Schema (`contracts/schemas/`);
- генерация Markdown-представления из канонического JSON.

```bash
python -m pip install -e ".[dev]"
sdlc validate ../specs/*.json
sdlc render ../specs/specification.json
```

Модули `runner`, `skills`, `policy`, `evidence`, `trust`, `adapters` добавятся в M1.
