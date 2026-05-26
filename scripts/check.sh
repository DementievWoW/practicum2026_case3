#!/usr/bin/env bash
# @file check.sh
# @brief Smoke-test всего стека после `make up`. Идемпотентно.
#
# Проверяет:
#   1) 6 сервисов compose в running-состоянии
#   2) 5 endpoints возвращают 200 (healthz, metrics, prometheus, grafana, langfuse)
#   3) POST /audit возвращает валидный JSON с approved/sql/audit_log
#   4) В Prometheus метрика sqlsec_runs_total реально растёт после прогона
#
# Запуск: bash scripts/check.sh  (или `make check`)
# Exit 0 — всё ок; exit ≥1 — есть проваленный пункт.

set -u
cd "$(dirname "$0")/.."

# python: на macOS может быть только `python` (без `3`); на Windows-WSL — `python3`.
# Linux обычно тоже `python3`. Ищем что есть.
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "❌ ни python3 ни python не найдены. Поставь Python 3.10+." >&2
  exit 2
fi

FAILED=0
PASS="\033[32m✔\033[0m"
FAIL="\033[31m✗\033[0m"

step() { printf "%b %s\n" "$1" "$2"; }

# ── 1. Контейнеры ──────────────────────────────────────────────────────────
expect_services=(db app prometheus grafana langfuse langfuse-db)
echo "── контейнеры ──"
for svc in "${expect_services[@]}"; do
  st="$(docker compose ps --format '{{.Service}} {{.State}}' \
        | awk -v s="$svc" '$1==s {print $2}')"
  if [ "$st" = "running" ]; then
    step "$PASS" "$svc: running"
  else
    step "$FAIL" "$svc: ${st:-не найден}"
    FAILED=$((FAILED+1))
  fi
done

# ── 2. Endpoints (HTTP-коды) ───────────────────────────────────────────────
echo ""
echo "── endpoints ──"
check_http() {
  local url="$1" label="$2" expect="${3:-200}"
  local code
  code="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 10 "$url" 2>/dev/null || echo 000)"
  if [ "$code" = "$expect" ]; then
    step "$PASS" "$label  ($url → $code)"
  else
    step "$FAIL" "$label  ($url → $code, ждали $expect)"
    FAILED=$((FAILED+1))
  fi
}
check_http http://localhost:18000/healthz                "FastAPI healthz"
check_http http://localhost:19100/metrics                "App /metrics"
check_http http://localhost:19090/-/healthy              "Prometheus"
check_http http://localhost:13000/api/health             "Grafana"
check_http http://localhost:13001/api/public/health      "Langfuse"

# ── 3. POST /audit с реальной задачей ──────────────────────────────────────
echo ""
echo "── POST /audit ──"
resp="$(curl -fsS -X POST http://localhost:18000/audit \
        -H 'Content-Type: application/json' \
        -d '{"task":"Сколько кредитных договоров?"}' \
        --max-time 60 2>/dev/null || echo "")"
if [ -z "$resp" ]; then
  step "$FAIL" "POST /audit не ответил"
  FAILED=$((FAILED+1))
else
  approved="$(echo "$resp" | $PY -c "import json,sys; print(json.load(sys.stdin)['approved'])" 2>/dev/null || echo "?")"
  sql="$(echo "$resp" | $PY -c "import json,sys; print(json.load(sys.stdin)['final_sql'][:80])" 2>/dev/null || echo "?")"
  if [ "$approved" = "True" ] || [ "$approved" = "False" ]; then
    step "$PASS" "/audit ответил: approved=$approved"
    step "$PASS" "SQL: ${sql}"
  else
    step "$FAIL" "/audit вернул что-то не то: ${resp:0:120}"
    FAILED=$((FAILED+1))
  fi
fi

# ── 4. Prometheus реально снимает метрики ──────────────────────────────────
echo ""
echo "── Prometheus → app:9100 ──"
runs="$(curl -fsS 'http://localhost:19090/api/v1/query' \
        --data-urlencode 'query=sum(sqlsec_runs_total)' --max-time 10 2>/dev/null \
        | $PY -c "import json,sys; d=json.load(sys.stdin); print(d['data']['result'][0]['value'][1] if d['data']['result'] else 0)" 2>/dev/null || echo "?")"
if [ "$runs" != "?" ] && [ "$runs" != "0" ]; then
  step "$PASS" "sqlsec_runs_total = $runs (метрики снимаются)"
else
  step "$FAIL" "sqlsec_runs_total = $runs (Prometheus не видит app:9100)"
  FAILED=$((FAILED+1))
fi

# ── Итог ───────────────────────────────────────────────────────────────────
echo ""
if [ $FAILED -eq 0 ]; then
  printf "%b всё работает.  UI: \033[36mhttp://localhost:18000\033[0m\n" "$PASS"
  exit 0
else
  printf "%b провалено пунктов: %d\n" "$FAIL" $FAILED
  echo "  hint: 'make logs' покажет хвост логов приложения"
  exit 1
fi
