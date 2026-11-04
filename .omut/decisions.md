# Decisions

- D1 [accepted 2026-10-01] Агент с tools вместо команд, одна команда на инсталляцию. → adr/0001-agent-first.md
- D2 [accepted 2026-10-01] Evals по результату в БД и миграции схемы через `PRAGMA user_version`. → adr/0002-evals-and-schema-migrations.md
- D3 [accepted 2026-10-24] Открыть репо (MIT). Два шага: `gh repo edit metravod/wimt_agent --visibility public` и отдельно видимость пакета GHCR, иначе `install.sh` у чужих упадёт на `docker pull`.
- D4 [accepted 2026-10-01] Автодеплой из CI выключен по умолчанию (`DEPLOY_ENABLED`): deploy-ключ на сервер добавляет только тот, кому это нужно.
- D5 [accepted 2026-11-04] Мета открытая: `.omut/` и `AGENTS.md` в репозитории, бейдж в `README.md` показывает её свежесть. `.omut/local/` в git не идёт.
- D6 [accepted 2026-11-04] Открытая часть описывает сам проект. Обстоятельства конкретной инсталляции (серверы, команда, её история) живут только в `.omut/local/`. Решение пользователя: «Давай относиться к проекту как к совершенно новому»
