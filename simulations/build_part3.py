"""
@file build_part3.py
@brief Ноутбуки 07, 08, 09 — sensitive access, SELECT *, no LIMIT.
"""

from build_helpers import md, code, footer_cell, COMMON_PREAMBLE


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 07 — Прямой доступ к чувствительным полям
# ════════════════════════════════════════════════════════════════════════════
def build_07() -> list:
    cells = []

    cells.append(md("""\
        # 07 — Прямой доступ к чувствительным полям

        > **`vuln_class`:** `DIRECT_SENSITIVE` · **Риск:** 6/10 · **CWE-200, CWE-359** · **152-ФЗ**

        Запрос вытаскивает колонки с **персональными данными** или **кредами** — пароли, СНИЛС, паспорт, номер карты, телефон, email — **без маскирования**. Сам по себе не атака, но классический канал утечки в bi-tools и отчётах аналитиков.
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        У тебя в школе есть журнал. В нём — оценки, домашние адреса
        и номера телефонов учеников.

        - **Плохо:** учительница ксерит **весь журнал** и раздаёт всем
          родителям — «вот, смотрите успеваемость». Заодно все узнают
          адреса и телефоны всех.
        - **Хорошо:** учительница пишет каждому родителю **отдельную
          записку** только с оценками их ребёнка. Чужих данных никто
          не видит.

        В БД: «весь журнал» — это `SELECT password_hash, passport, phone FROM users`.
        «Маскированная записка» — `SELECT login, LEFT(phone, 3) || '***' FROM users`.
        """))

    cells.append(md("""\
        ## 1. Setup — таблица клиентов с PII
        """))

    cells.append(code(COMMON_PREAMBLE + """

def setup_clients_pii():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute(\"\"\"
        CREATE TABLE clients (
            id            INTEGER PRIMARY KEY,
            login         TEXT,
            full_name     TEXT,
            passport      TEXT,          -- ⚠️ ПДн
            phone         TEXT,          -- ⚠️ ПДн
            card_number   TEXT,          -- ⚠️ платёжные данные
            password_hash TEXT           -- ⚠️ кред
        )\"\"\")
    cur.executemany(
        "INSERT INTO clients (login, full_name, passport, phone, card_number, password_hash) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("ivanov",  "Иван И.",   "4500 123456", "+79161234567", "4276 1234 5678 9012", "h_iv"),
            ("petrova", "Мария П.",  "4500 654321", "+79169876543", "5469 0001 0002 0003", "h_pet"),
            ("smith",   "John S.",   "P12345678",   "+1234567890",  "4242 4242 4242 4242", "h_sm"),
        ],
    )
    conn.commit()
    return conn


conn = setup_clients_pii()
section("Таблица clients (минус password_hash)")
show_result(conn.execute("SELECT id, login, full_name FROM clients").fetchall())
"""))

    cells.append(md("""\
        ## 2. Уязвимый «отчёт» — аналитик хочет CSV для Excel
        """))

    cells.append(code("""\
##
# @brief УЯЗВИМАЯ функция: тащит ПДн без маскирования.
# @warning  Утечка СНИЛС / паспорта / карты в CSV → инцидент 152-ФЗ.
def export_clients_BAD(conn):
    sql = "SELECT login, full_name, passport, phone, card_number FROM clients"
    print(f"  SQL: {sql}")
    return conn.execute(sql).fetchall()


section("Аналитик выгружает «всех клиентов» — что попадает в CSV")
rows = export_clients_BAD(conn)
for r in rows:
    print(f"  {r}")
"""))

    cells.append(md("""\
        ## 3. Аудитор Phase 1 — `R009-sensitive-columns`

        Чек-лист имён колонок (мы переиспользуем словарь из ADR-0005,
        раздел `kb.pii`). В проде ещё проверяется, не обёрнута ли колонка
        маскирующей функцией (`coalesce`, `mask`, `digest`, `left`, `substring`).
        """))

    cells.append(code("""\
SENSITIVE_PATTERNS = [
    (r"(?i)^(password|passwd|pwd|secret|api[_-]?key|token|access[_-]?token)$",
     "critical", 8),
    (r"(?i)^(card[_-]?(number|num|no)|pan|cvv|cvc)$",
     "critical", 8),
    (r"(?i)^(passport|inn|snils|ogrn|ssn|social[_-]?security)$",
     "high", 7),
    (r"(?i)^(email|phone|mobile|tel)$",
     "medium", 5),
    (r"(?i)^(dob|birth(_?date|day))$",
     "medium", 5),
]


##
# @brief Phase 1 R009 — детект чувствительных колонок в SELECT.
# @details
#   1. Парсим SELECT-колонки (упрощённо).
#   2. Для каждой проверяем regex.
#   3. Не флагаем, если колонка обёрнута в маскирующую функцию.
def audit_R009_sensitive(sql_text):
    findings = []
    m = re.match(r"\\s*SELECT\\s+(.+?)\\s+FROM\\b", sql_text,
                 re.IGNORECASE | re.DOTALL)
    if not m:
        return findings
    columns_raw = m.group(1)
    columns = [c.strip() for c in columns_raw.split(",")]
    for col_expr in columns:
        # Если колонка завёрнута в маскирующую функцию — пропускаем
        if re.search(r"\\b(coalesce|mask|digest|hash|left|substring|pgp_sym_decrypt)\\s*\\(",
                     col_expr, re.IGNORECASE):
            continue
        # Берём последний идентификатор как имя колонки
        last_id_match = re.findall(r"\\b\\w+\\b", col_expr)
        if not last_id_match:
            continue
        col_name = last_id_match[-1]
        for pat, sev, score in SENSITIVE_PATTERNS:
            if re.match(pat, col_name):
                findings.append({
                    "rule_id":       "R009-sensitive-columns",
                    "vuln_class":    "DIRECT_SENSITIVE",
                    "severity":      sev, "risk_score": score,
                    "message":       f"Колонка {col_name!r} — чувствительная",
                    "evidence_refs": ["CWE-200", "CWE-359"],
                })
                break
    return findings


section("Аудитор по уязвимому SQL")
for f in audit_R009_sensitive("SELECT login, full_name, passport, phone, card_number FROM clients"):
    print_finding(f)
"""))

    cells.append(md("""\
        ## 4. Безопасный отчёт — view с маскированием
        """))

    cells.append(code("""\
##
# @brief Безопасный отчёт: маскируем PII.
def export_clients_GOOD(conn):
    sql = \"\"\"
        SELECT
            login,
            full_name,
            substr(passport, 1, 4) || '******'           AS passport_masked,
            substr(phone, 1, 3) || '***' || substr(phone, -2) AS phone_masked
        FROM clients
    \"\"\"
    return conn.execute(sql).fetchall()


section("Маскированный CSV")
for r in export_clients_GOOD(conn):
    print(f"  {r}")


section("Аудитор по маскированному SQL")
fs = audit_R009_sensitive(export_clients_GOOD.__doc__ or \"\"\"
    SELECT login, full_name,
           substr(passport, 1, 4) || '******' AS passport_masked,
           substr(phone, 1, 3) || '***' || substr(phone, -2) AS phone_masked
    FROM clients
\"\"\")
if fs:
    for f in fs:
        print_finding(f)
else:
    print("  ✅ Чувствительных колонок не найдено (всё под маскирующими функциями).")
"""))

    cells.append(footer_cell("07-direct-sensitive-access"))
    return cells


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 08 — Избыточный SELECT *
# ════════════════════════════════════════════════════════════════════════════
def build_08() -> list:
    cells = []

    cells.append(md("""\
        # 08 — Избыточный SELECT *

        > **`vuln_class`:** `SELECT_STAR` · **Риск:** 5/10 · **CWE-1295**

        `SELECT *` — не уязвимость **сама по себе**, но классический «множитель» для других. Раскрывает в выборке **все** колонки таблицы, включая чувствительные, которые приложению/UI не нужны.
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        Тебе нужны **только конфеты** из коробки шоколада. Ты приходишь
        и говоришь продавцу: «дай **всё**». Он даёт тебе всю коробку,
        включая обёртки, разделители, описание состава, штрих-код.

        - **Плохо:** ты тащишь домой всю коробку и аккуратно достаёшь
          конфеты. Лишнее — мусор, лишний вес, лишнее время.
        - **Хорошо:** говоришь «дай две вишнёвые и одну с орехом» —
          получаешь ровно то, что нужно.

        В БД: `SELECT *` тащит все колонки, **включая** `password_hash`,
        `internal_notes`, `migration_token`. Тратится трафик, кеш, безопасность.
        """))

    cells.append(md("""\
        ## 1. Setup
        """))

    cells.append(code(COMMON_PREAMBLE + """

def setup_users_full():
    conn = sqlite3.connect(":memory:")
    conn.execute(\"\"\"
        CREATE TABLE users (
            id              INTEGER PRIMARY KEY,
            login           TEXT,
            full_name       TEXT,
            email           TEXT,
            password_hash   TEXT,          -- ⚠️
            internal_notes  TEXT,          -- ⚠️ внутренние заметки (NDA)
            migration_token TEXT           -- ⚠️ кред
        )\"\"\")
    conn.executemany(
        "INSERT INTO users (login, full_name, email, password_hash, internal_notes, migration_token) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("admin",  "Анна А.", "anna@ex.com",  "h_admin",  "VIP клиент",   "tk_admin_xyz"),
            ("bob",    "Боб Б.",  "bob@ex.com",   "h_bob",    "Жалоба #123",  "tk_bob_qqq"),
        ],
    )
    conn.commit()
    return conn


conn = setup_users_full()
"""))

    cells.append(md("""\
        ## 2. Уязвимый запрос — нужен список пользователей для UI
        """))

    cells.append(code("""\
##
# @brief УЯЗВИМАЯ функция: SELECT * — выбирает всё, что есть.
# @warning  Утечка password_hash, migration_token, internal_notes в UI/логи.
def list_users_BAD(conn):
    sql = "SELECT * FROM users"
    print(f"  SQL: {sql}")
    return conn.execute(sql).fetchall()


section("Что попадает в UI/логи")
for r in list_users_BAD(conn):
    print(f"  {r}")
"""))

    cells.append(md("""\
        ## 3. Аудитор Phase 1 — `R001-select-star`
        """))

    cells.append(code("""\
##
# @brief Phase 1 R001 — детект SELECT *.
# @note  Игнорируем COUNT(*), row_to_json(t.*) обрабатывается отдельно (повышаем severity).
def audit_R001_select_star(sql_text):
    findings = []
    # SELECT * (с возможным алиасом t.*) — но НЕ COUNT(*) и НЕ внутри агрегата
    pattern = r"SELECT\\s+(?:DISTINCT\\s+)?(?:\\w+\\.)?\\*"
    for m in re.finditer(pattern, sql_text, re.IGNORECASE):
        snippet = m.group(0)
        # Грубая проверка на COUNT/row_to_json
        ctx_start = max(0, m.start() - 25)
        ctx = sql_text[ctx_start:m.start()].lower()
        if "count(" in ctx or "row_to_json(" in ctx or "to_jsonb(" in ctx:
            continue
        findings.append({
            "rule_id":       "R001-select-star",
            "vuln_class":    "SELECT_STAR",
            "severity":      "medium", "risk_score": 5,
            "message":       f"{snippet!r} — выбираются все колонки, включая возможно чувствительные",
            "evidence_refs": ["CWE-1295"],
        })
    return findings


section("Аудитор по разным запросам")
for sql in [
    "SELECT * FROM users",
    "SELECT u.* FROM users u JOIN roles r ON u.role_id = r.id",
    "SELECT COUNT(*) FROM users",                         # это норм
    "SELECT id, login, full_name FROM users",             # это норм
]:
    print(f"\\n SQL: {sql}")
    fs = audit_R001_select_star(sql)
    if fs:
        for f in fs:
            print_finding(f)
    else:
        print("  ✅ ok")
"""))

    cells.append(md("""\
        ## 4. Phase 1b — раскрытие `*` через `information_schema.columns`

        В проде sandbox-БД содержит схему. Раскрываем `*` в реальные колонки
        и прогоняем правило `R009` (sensitive columns) — это даёт ещё один,
        **более тяжёлый** finding.
        """))

    cells.append(code("""\
##
# @brief Имитация Phase 1b — раскрываем SELECT * через PRAGMA table_info
# @note  В PG было бы information_schema.columns, тут — PRAGMA SQLite.
def expand_star_and_check(conn, sql_text):
    m = re.match(r"\\s*SELECT\\s+\\*\\s+FROM\\s+(\\w+)", sql_text, re.IGNORECASE)
    if not m:
        return []
    table = m.group(1)
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    print(f"  Раскрываем SELECT * → колонки: {cols}")
    # Прогоняем тот же regex R009
    suspicious = []
    for col in cols:
        for pat, sev, score in [
            (r"(?i)^(password|passwd|pwd|secret|api[_-]?key|token|access[_-]?token|migration[_-]?token)$", "critical", 8),
            (r"(?i)^internal(_notes|_data)?$", "medium", 6),
        ]:
            if re.match(pat, col):
                suspicious.append((col, sev, score))
                break
    return suspicious


susp = expand_star_and_check(conn, "SELECT * FROM users")
section("Phase 1b — чувствительные колонки в раскрытом *")
for col, sev, score in susp:
    print_finding({
        "rule_id":       "R001+R009-star-leaks-sensitive",
        "vuln_class":    "DIRECT_SENSITIVE",
        "severity":      sev, "risk_score": score,
        "message":       f"SELECT * раскроет {col!r} — это чувствительная колонка",
        "evidence_refs": ["CWE-200", "CWE-1295"],
    })
"""))

    cells.append(md("""\
        ## 5. Безопасная версия — явный список колонок
        """))

    cells.append(code("""\
##
# @brief Безопасная функция: явный список колонок.
def list_users_GOOD(conn):
    sql = "SELECT id, login, full_name, email FROM users"
    return conn.execute(sql).fetchall()


section("Безопасная версия")
for r in list_users_GOOD(conn):
    print(f"  {r}")
"""))

    cells.append(footer_cell("08-select-star"))
    return cells


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 09 — Неограниченный LIMIT (No Pagination)
# ════════════════════════════════════════════════════════════════════════════
def build_09() -> list:
    cells = []

    cells.append(md("""\
        # 09 — Неограниченный LIMIT (нет пагинации)

        > **`vuln_class`:** `NO_PAGINATION` · **Риск:** 4/10 · **CWE-770**

        Запрос без `LIMIT` на большой таблице тащит всё в память приложения. На пороге одобрения (`RISK_THRESHOLD = 4.0`) — сам по себе пропустится, но в комбинации с `SELECT *` (5) или `DIRECT_SENSITIVE` (6) превышает.
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        Ты приходишь в библиотеку и говоришь библиотекарю:
        «**дай мне все книги** про динозавров».

        - **Плохо:** библиотекарь катит тебе **5 тележек** с 500 книгами.
          Ты не унесёшь, бросишь половину, и всем плохо.
        - **Хорошо:** «**дай мне 10 книг** про динозавров, отсортированных
          по году издания». Берёшь 10, читаешь, возвращаешься за следующими.

        Это **пагинация**. В SQL — `LIMIT 10`. Без LIMIT БД отдаст
        ВСЁ — миллион строк, гигабайты трафика, OOM в приложении.
        """))

    cells.append(md("""\
        ## 1. Setup — большая таблица
        """))

    cells.append(code(COMMON_PREAMBLE + """

def setup_orders():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, ts TEXT)")
    # 10000 строк — для демо «большой» таблицы
    orders = [(i, i % 100, i * 1.5, f"2026-01-{(i % 28) + 1:02d}") for i in range(1, 10001)]
    conn.executemany("INSERT INTO orders (id, user_id, amount, ts) VALUES (?, ?, ?, ?)", orders)
    conn.commit()
    return conn


conn = setup_orders()
n = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
print(f"В таблице orders: {n} строк")
"""))

    cells.append(md("""\
        ## 2. Уязвимый запрос — нет LIMIT
        """))

    cells.append(code("""\
##
# @brief УЯЗВИМАЯ функция: тянет все заказы.
def fetch_all_orders_BAD(conn):
    sql = "SELECT id, user_id, amount, ts FROM orders ORDER BY ts DESC"
    print(f"  SQL: {sql}")
    t0 = time.time()
    rows = conn.execute(sql).fetchall()
    dt = time.time() - t0
    print(f"  Получено {len(rows)} строк за {dt*1000:.1f} мс")
    return rows


section("Уязвимый вызов — тянет всё")
rows = fetch_all_orders_BAD(conn)
"""))

    cells.append(md("""\
        ## 3. Маскированная версия — `LIMIT 1_000_000`

        Иногда разработчик «защищается» гигантским LIMIT — это та же
        проблема, просто менее очевидная.
        """))

    cells.append(code("""\
##
# @brief Маскированная версия: LIMIT есть, но абсурдный.
def fetch_orders_BAD_huge_limit(conn):
    sql = "SELECT id, user_id, amount, ts FROM orders ORDER BY ts DESC LIMIT 1000000"
    rows = conn.execute(sql).fetchall()
    print(f"  Получено {len(rows)} строк (LIMIT 1000000)")


fetch_orders_BAD_huge_limit(conn)
"""))

    cells.append(md("""\
        ## 4. Аудитор Phase 1 — `R004-no-limit`
        """))

    cells.append(code("""\
##
# @brief Phase 1 R004 — детект SELECT без LIMIT или с гигантским LIMIT.
def audit_R004_no_limit(sql_text):
    findings = []
    is_select = bool(re.match(r"\\s*SELECT\\b", sql_text, re.IGNORECASE))
    if not is_select:
        return findings
    # Игнорируем агрегаты (мало строк)
    if re.search(r"\\b(COUNT|SUM|AVG|MIN|MAX|GROUP\\s+BY)\\b", sql_text, re.IGNORECASE):
        return findings

    limit_m = re.search(r"\\bLIMIT\\s+(\\d+)", sql_text, re.IGNORECASE)
    if limit_m is None:
        findings.append({
            "rule_id":       "R004-no-limit",
            "vuln_class":    "NO_PAGINATION",
            "severity":      "low", "risk_score": 4,
            "message":       "SELECT без LIMIT — потенциальный DoS",
            "evidence_refs": ["CWE-770"],
        })
    else:
        n = int(limit_m.group(1))
        if n > 10_000:
            findings.append({
                "rule_id":       "R004-no-limit",
                "vuln_class":    "NO_PAGINATION",
                "severity":      "low", "risk_score": 3,
                "message":       f"LIMIT {n} — избыточен, по сути нет пагинации",
                "evidence_refs": ["CWE-770"],
            })
    return findings


section("Аудитор по разным SQL")
for sql in [
    "SELECT id, user_id FROM orders ORDER BY ts DESC",
    "SELECT id, user_id FROM orders ORDER BY ts DESC LIMIT 1000000",
    "SELECT id, user_id FROM orders ORDER BY ts DESC LIMIT 50",
    "SELECT COUNT(*) FROM orders",  # это норм — агрегат
]:
    print(f"\\n SQL: {sql}")
    fs = audit_R004_no_limit(sql)
    if fs:
        for f in fs:
            print_finding(f)
    else:
        print("  ✅ ok")
"""))

    cells.append(md("""\
        ## 5. Безопасная версия — keyset pagination
        """))

    cells.append(code("""\
##
# @brief Безопасная функция: keyset pagination.
# @details
#   Вместо OFFSET (медленно на больших таблицах) — фильтр по id курсора.
#   Каждый запрос — стабильно O(page_size).
def fetch_orders_GOOD(conn, last_seen_id: int = None, page_size: int = 50):
    if last_seen_id is None:
        sql = "SELECT id, user_id, amount, ts FROM orders ORDER BY id DESC LIMIT ?"
        return conn.execute(sql, (page_size,)).fetchall()
    sql = "SELECT id, user_id, amount, ts FROM orders WHERE id < ? ORDER BY id DESC LIMIT ?"
    return conn.execute(sql, (last_seen_id, page_size)).fetchall()


section("Первая страница (50 строк)")
page1 = fetch_orders_GOOD(conn, page_size=5)  # для демо берём 5
for r in page1:
    print(f"  {r}")


section("Следующая страница — last_seen_id = id последнего из page1")
last_id = page1[-1][0]
page2 = fetch_orders_GOOD(conn, last_seen_id=last_id, page_size=5)
for r in page2:
    print(f"  {r}")
"""))

    cells.append(footer_cell("09-no-pagination"))
    return cells
