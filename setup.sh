#!/usr/bin/env bash
# Первый запуск стека: спрашивает LLM-ключ → раскладывает env/секреты → docker compose up.
# Идемпотентно: повторный запуск не перетирает уже заполненные файлы.
set -e

cd "$(dirname "$0")"

# ── проверки окружения ───────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || { echo "❌ docker не найден. Установи Docker Desktop и перезапусти."; exit 1; }
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "❌ docker compose не найден"; exit 1
fi
[ -f .env.example ]      || { echo "❌ нет .env.example — запускай из корня репозитория"; exit 1; }
[ -f docker-compose.yml ] || { echo "❌ нет docker-compose.yml — запускай из корня репозитория"; exit 1; }

# ── 1. .env из шаблона ───────────────────────────────────────────────────────
if [ -f .env ]; then
  echo "· .env уже есть, не трогаю"
else
  cp .env.example .env
  echo "✓ .env создан из .env.example"
fi

# ── 2. секрет с LLM-ключом ───────────────────────────────────────────────────
mkdir -p secrets
if [ -s secrets/llm_api_key ]; then
  echo "· secrets/llm_api_key уже заполнен, не перезаписываю"
  echo "  (если ключ протух — отредактируй файл вручную и запусти: $DC restart app)"
else
  echo
  echo "Вставь свой LLM API-ключ и нажми Enter."
  echo "(Если ключа нет — просто Enter: приложение поднимется на mock-LLM.)"
  printf "Ключ: "
  read -r KEY
  KEY="${KEY//$'\r'/}"   # на случай Windows-перевода строки в буфере
  if [ -n "$KEY" ]; then
    printf "%s" "$KEY" > secrets/llm_api_key
    chmod 600 secrets/llm_api_key
    echo "✓ ключ записан в secrets/llm_api_key"
  else
    : > secrets/llm_api_key
    echo "· ключ не задан → будет MockLLMClient (видно в логах app)"
  fi
fi

# ── 3. поднять стек ──────────────────────────────────────────────────────────
echo
echo "Поднимаю docker-стек…"
$DC up -d --build

# ── 4. дождаться готовности app ──────────────────────────────────────────────
echo
printf "Жду готовности app (до 60 сек) "
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:18000/healthz >/dev/null 2>&1; then
    echo " ✓"
    READY=1
    break
  fi
  printf "."
  sleep 1
done
[ "${READY:-}" = "1" ] || echo " (не дождался — проверь '$DC logs app')"

# ── 5. что открывать ─────────────────────────────────────────────────────────
cat <<EOF

Готово. Открой в браузере:
  Приложение   http://localhost:18000
  Grafana      http://localhost:13000   admin / admin
  Langfuse     http://localhost:13001   admin@example.com / admin1234
  Prometheus   http://localhost:19090

Полезные команды:
  $DC ps                          # статус сервисов
  $DC logs -f app                 # логи приложения
  $DC restart app                 # перезапустить app (например, после смены ключа)
  $DC down                        # остановить стек (данные сохраняются)
EOF
