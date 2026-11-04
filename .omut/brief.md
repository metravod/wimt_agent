---
status: active
updated: 2026-11-04
verified: 2026-11-04
by: claude-code/opus-5.5
adr: adr/
---
## Why
Telegram-ассистент небольшой команды: статусы, дейли и отсутствия через свободный чат, без команд и меню. Цели: минимум кода, установка для не-инженеров (`install.sh`), код легко ревьюить.

## What it is
~1.1k строк Python в `app/`: агент поверх OpenAI (gpt-5.4-nano) с tools, SQLite, планировщик (дейли, недельные отчёты, предупреждения о праздниках). Миграции через `db.MIGRATIONS` + `PRAGMA user_version`.
`evals/`: 20 кейсов с проверкой по результату в БД, `python -m evals`, нужен ключ модели. Тесты в `tests/`: `python -m pytest`.
Решения в `adr/` (0001 агент вместо команд, 0002 evals и миграции, 0003 предупреждение о праздниках). Установка и запуск описаны в `README.md`, `install.sh`, `Dockerfile`.
Как чинится поведение: странный ответ → кейс в `evals/cases.py` → фикс → прогон evals → выкатка с бэкапом БД.

## Where it lives
Где работает конкретная инсталляция, не здесь: это `local/instance.md` каждой копии (D6).
- GitHub: github.com/metravod/wimt_agent, **private**, MIT LICENSE, открыть запланировано (D3). · how: gh repo view metravod/wimt_agent --json visibility · seen 2026-11-04
- CI: `.github/workflows/build.yaml` (тесты и образ `ghcr.io/metravod/wimt_agent`), `.github/workflows/omut.yml` (свежесть меты, бейдж). · how: gh run list -R metravod/wimt_agent · seen 2026-11-04

## Now
Работает у живой команды. Только что добавлены предупреждение о праздниках и защита от выключенных праздников (ADR-0003), мета открыта (D5).
**Verified:** 2026-11-04: тесты 24/24; evals 20/20 на gpt-5.4-nano.
**Not verified:** предупреждение о празднике вживую, пока только тестами; видимость пакета GHCR; перенесённые выходные 2026–2027 (`holidays` 0.105 на 2026 их не содержит).

## Next
1. Переносы выходных: 31.12.2026 и далее бот может счесть рабочими, решить, нужен ли список дополнительных выходных (ADR-0003)
2. Открыть репо и пакет GHCR (D3)
