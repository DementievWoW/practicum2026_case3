# Langfuse — настройка трейсов LLM-цепочек

Langfuse в нашем compose поднят сам собой (контейнер `sqlsec-langfuse`,
порт **13001**). Но **трейсы туда не идут**, пока в `.env` нет API-ключей —
наш пайплайн в этом режиме использует `StubTracer` (трейсы в памяти).

Если просто хочется прогнать демо без трейсов — пропусти это руководство.
StubTracer не мешает работе и метрики Grafana всё равно идут.

## Зачем настраивать (5 секунд)

С реальными ключами в Langfuse будут видны:
- каждый прогон `/audit` как **trace** с длительностью
- спаны `pipeline` → `generator` → `auditor` → `reflector`
- scores `final_risk`, `approved` для фильтрации
- LLM-промпт+ответ (если включить детализацию)

Это полезно для:
- отладки long-tail кейсов (видно где модель «застряла»)
- демо: красивая визуализация цепочки на защите

## Настройка (5 минут, разово)

### 1. Открой UI

```
http://localhost:13001
```

### 2. Войди

**Если БД свежая** (свежий клон, никто раньше Langfuse не открывал):
дефолтный аккаунт создаётся автоматически из `docker-compose.yml`:

| Поле | Значение |
|---|---|
| Email | `admin@example.com` |
| Password | `admin1234` |

**Если уже логинился раньше** — Langfuse init НЕ создаёт повторно
дефолтного юзера, если в БД уже есть хоть кто-то. Войди под тем
аккаунтом, что создал раньше.

**Если потерял пароль / забыл аккаунт** — снести volume и начать заново:
```bash
docker compose down
docker volume rm sqlsec_langfuse_db_data
docker compose up -d langfuse-db langfuse
# теперь admin@example.com / admin1234 сработает
```

⚠ Это локальная разработка — для прода не использовать дефолтные ключи.

### 3. Создай проект (если не создан автоматически)

В организации `sqlsec` (она создаётся автоматически из
`LANGFUSE_INIT_ORG_NAME`):

- Левое меню → **+ New project**
- Имя: `sqlsec-prod` (или любое)
- **Create**

### 4. Создай API keys

- Settings (шестерёнка слева) → **API Keys** → **+ Create API key**
- Появится:
  - **Public key**: `pk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
  - **Secret key**: `sk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

⚠ **Secret key показывается только один раз** — скопируй сразу.

### 5. Положи ключи в .env

В корне репозитория, отредактируй `.env`:

```dotenv
LANGFUSE_HOST=http://langfuse:3000
LANGFUSE_PUBLIC_KEY=pk-lf-...     # вставь свой
LANGFUSE_SECRET_KEY=sk-lf-...     # вставь свой
```

Важно: `LANGFUSE_HOST=http://langfuse:3000` — это **внутренний** URL внутри
docker network. Не `localhost:13001` (это с хоста).

### 6. Перезапусти app

```bash
docker compose up -d app
```

(только `app`, не весь стек — Langfuse и его БД не трогаем).

### 7. Прогон → проверка

```bash
curl -s -X POST localhost:18000/audit \
  -H 'Content-Type: application/json' \
  -d '{"task":"Сколько кредитных договоров?"}' >/dev/null
```

В UI Langfuse:
- Главная → **Traces** → должна появиться запись `sql_security_pipeline`
- Click на трейс → видишь спаны, длительности, scores

## Объяснить коллеге

> Просто перешли ему эту страницу. Все 7 шагов одной командой:
>
> 1. Запустил compose, открыл http://localhost:13001
> 2. Залогинился admin@example.com / admin1234
> 3. Создал проект, скопировал `pk-lf-…` и `sk-lf-…`
> 4. Положил их в `.env`
> 5. `docker compose up -d app`
> 6. Дёрнул `/audit`
> 7. Трейс появился в Langfuse UI

## Почему нельзя сделать это автоматически

Langfuse v2 генерирует API-ключи **только через UI** (tRPC через
NextAuth-сессию). Программно создать ключи через `curl` нельзя без
эмуляции браузерной сессии — это слишком хрупко.

Это разовый ручной шаг для каждой среды (dev / staging / prod), как и
в любом другом сервисе с self-host управлением.

## Прод-режим (не для локального демо)

Для прод-окружения замените в `docker-compose.yml`:

```yaml
NEXTAUTH_SECRET: ${LANGFUSE_NEXTAUTH_SECRET:?required}
SALT: ${LANGFUSE_SALT:?required}
# убрать default'ы localdev-...
# убрать LANGFUSE_INIT_USER_PASSWORD: admin1234
```

И сгенерируйте уникальные secret/salt:

```bash
echo "LANGFUSE_NEXTAUTH_SECRET=$(openssl rand -base64 32)" >> .env
echo "LANGFUSE_SALT=$(openssl rand -base64 32)" >> .env
```
