# SQL Security Multi-Agent — удобные команды для коллег.
# Запускать из корня репо: `make <цель>`. Без аргументов — `help`.
#
# Все цели safe to re-run (idempotent), кроме `clean`.

# По умолчанию — справка
.DEFAULT_GOAL := help

# Подавляет «Entering directory» и подобный шум make
MAKEFLAGS += --no-print-directory

COMPOSE = docker compose

# ─── help ────────────────────────────────────────────────────────────────────
.PHONY: help
help:                                  ## показать список команд (эта справка)
	@printf "\033[1mSQL Security Multi-Agent\033[0m\n\n"
	@printf "Один раз (после git clone):\n"
	@printf "  \033[36mmake setup\033[0m         подготовить .env + secrets/ + Langfuse-secrets\n"
	@printf "  \033[36mmake up\033[0m            собрать образы и поднять 6 сервисов\n"
	@printf "  \033[36mmake check\033[0m         smoke-test: все endpoints отвечают?\n\n"
	@printf "Каждодневное:\n"
	@grep -hE '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | awk -F':.*?##' \
	  '{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ─── lifecycle ───────────────────────────────────────────────────────────────
.PHONY: setup
setup:                                 ## создать .env + secrets/ (идемпотентно)
	@bash scripts/setup.sh

.PHONY: up
up:                                    ## собрать образы и поднять весь стек
	@$(COMPOSE) up -d --build
	@echo ""
	@echo "Ждём 10 сек пока seeder + langfuse инициализируются…"
	@sleep 10
	@$(MAKE) ps

.PHONY: down
down:                                  ## остановить стек (volume сохраняются)
	@$(COMPOSE) down

.PHONY: clean
clean:                                 ## ⚠ остановить + удалить volumes (данные БД пропадут)
	@$(COMPOSE) down -v
	@rm -f data/embeddings_cache.json

.PHONY: ps
ps:                                    ## статус всех сервисов
	@$(COMPOSE) ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'

.PHONY: logs
logs:                                  ## хвост логов приложения (Ctrl-C для выхода)
	@$(COMPOSE) logs -f app

.PHONY: restart
restart:                               ## пересобрать только app (после правок кода)
	@$(COMPOSE) up -d --build app
	@sleep 3
	@$(MAKE) ps

# ─── проверки ────────────────────────────────────────────────────────────────
.PHONY: check
check:                                 ## smoke-test: 5 endpoints + один /audit
	@bash scripts/check.sh

.PHONY: ex-eval
ex-eval:                               ## прогнать 26 задач EX-eval (нужен LLM API key)
	@set -a; . ./.env; set +a; \
	 DB_PORT=15432 PYTHONPATH=.:src python3 scripts/ex_eval.py

.PHONY: adv-eval
adv-eval:                              ## adversarial-eval: hints OFF vs ON
	@set -a; . ./.env; set +a; \
	 DB_PORT=15432 PYTHONPATH=.:src python3 scripts/adv_eval.py

# ─── окна (просто открывалки, без логики) ──────────────────────────────────
.PHONY: open
open:                                  ## вывести URL'ы всех сервисов
	@echo "FastAPI UI:  http://localhost:18000"
	@echo "Prometheus:  http://localhost:19090"
	@echo "Grafana:     http://localhost:13000  (admin/admin)"
	@echo "Langfuse:    http://localhost:13001  (admin@example.com/admin1234 на свежей БД)"
	@echo "Postgres:    psql postgresql://distr_user:pass@localhost:15432/demo_db"
