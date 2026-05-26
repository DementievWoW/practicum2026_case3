#!/usr/bin/env bash
# @file setup.sh
# @brief Подготовка свежего клона к `docker compose up`. Идемпотентно.
#
# Делает три вещи:
#   1) .env из .env.example, если ещё нет;
#   2) пустой secrets/llm_api_key (compose требует файл — пустой = MockLLM);
#   3) генерирует LANGFUSE_NEXTAUTH_SECRET / SALT через openssl, если они пустые
#      в .env (можно пропустить и положиться на compose-defaults).
#
# Запуск из корня репо:
#   bash scripts/setup.sh
#   docker compose up -d --build

set -euo pipefail
cd "$(dirname "$0")/.."

# 1) .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✔ создан .env из .env.example"
else
  echo "= .env уже есть"
fi

# 2) secrets/llm_api_key (пустой = MockLLM, реальный = подложите свой ключ)
mkdir -p secrets
if [ ! -s secrets/llm_api_key ]; then
  : > secrets/llm_api_key
  echo "✔ создан пустой secrets/llm_api_key (MockLLM по умолчанию)"
  echo "  Чтобы использовать реальную LLM: echo 'sk-...' > secrets/llm_api_key"
else
  echo "= secrets/llm_api_key уже заполнен"
fi

# 3) Langfuse secrets — генерим, если пусто в .env
if ! grep -q '^LANGFUSE_NEXTAUTH_SECRET=..' .env 2>/dev/null; then
  ns="$(openssl rand -base64 32)"
  sed -i.bak "s|^LANGFUSE_NEXTAUTH_SECRET=.*|LANGFUSE_NEXTAUTH_SECRET=${ns}|" .env
  rm -f .env.bak
  echo "✔ LANGFUSE_NEXTAUTH_SECRET сгенерирован"
fi
if ! grep -q '^LANGFUSE_SALT=..' .env 2>/dev/null; then
  s="$(openssl rand -base64 32)"
  sed -i.bak "s|^LANGFUSE_SALT=.*|LANGFUSE_SALT=${s}|" .env
  rm -f .env.bak
  echo "✔ LANGFUSE_SALT сгенерирован"
fi

echo ""
echo "Готово. Следующий шаг:"
echo "  docker compose up -d --build"
echo ""
echo "Опц.: подключить трейсинг LLM-цепочек в Langfuse:"
echo "  см. docs/langfuse.md (5 минут разово на UI: http://localhost:13001)"
