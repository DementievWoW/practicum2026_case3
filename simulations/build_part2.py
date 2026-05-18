"""
@file build_part2.py
@brief Ноутбуки 04, 05, 06 — DML без WHERE, privilege escalation, PL/pgSQL EXECUTE.
"""

from build_helpers import md, code, footer_cell, COMMON_PREAMBLE


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 04 — UPDATE/DELETE без WHERE
# ════════════════════════════════════════════════════════════════════════════
def build_04() -> list:
    cells = []

    cells.append(md("""\
        # 04 — UPDATE / DELETE без WHERE

        > **`vuln_class`:** `DML_NO_WHERE` · **Риск:** 9/10 · **CWE-1284**

        Запрос модификации данных без условия `WHERE` (или с предикатом, который всегда истинный — `WHERE 1=1`) затрагивает **все строки** таблицы. Часто — результат опечатки или копипасты, в проде сразу становится инцидентом.
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        У тебя в комнате стоят 1000 коробок. Мама говорит:
        «**Покрась коробку #42 в красный**». Это правильное задание — ты
        находишь коробку 42 и красишь её.

        А теперь представь, что мама забыла назвать номер: «**Покрась коробку**».
        Какую? Все? Ты в растерянности — и красишь **все 1000 коробок**.
        Восстановить старый цвет уже нельзя.

        В SQL то же самое: `UPDATE clients SET balance = 0` — где у тебя
        нет `WHERE`, БД применит к **всей таблице**. У всех клиентов
        баланс станет 0. Восстановить — только из бэкапа.
        """))

    cells.append(md("""\
        ## 1. Setup — таблица клиентов с балансами
        """))

    cells.append(code(COMMON_PREAMBLE + """

##
# @brief Создаёт мок-БД клиентов с балансами.
def setup_clients_db():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute(\"\"\"
        CREATE TABLE clients (
            client_id INTEGER PRIMARY KEY,
            full_name TEXT,
            balance   REAL
        )\"\"\")
    cur.executemany(
        "INSERT INTO clients (full_name, balance) VALUES (?, ?)",
        [("Иван И.", 1500.50), ("Мария П.", 87000.00), ("Олег С.", 250.00),
         ("Анна Р.", 1_000_000.00), ("Виктор М.", 0.50)],
    )
    conn.commit()
    return conn


conn = setup_clients_db()
section("Состояние таблицы clients ДО запроса")
show_result(conn.execute("SELECT * FROM clients").fetchall())
"""))

    cells.append(md("""\
        ## 2. Опасный запрос — задумано обнулить одного клиента, забыли WHERE
        """))

    cells.append(code("""\
##
# @brief УЯЗВИМАЯ функция: разработчик хотел обнулить баланс одного клиента.
# @warning Забыли `WHERE client_id = ...` — обнулится ВСЯ таблица.
def zero_balance_BAD(conn, client_id: int):
    sql = "UPDATE clients SET balance = 0"  # ← АНТИПАТТЕРН: нет WHERE
    print(f"  Выполняется: {sql}")
    conn.execute(sql)
    conn.commit()


section("УЯЗВИМЫЙ вызов: думали обнулить #3, но...")
zero_balance_BAD(conn, 3)

section("Состояние таблицы ПОСЛЕ — все балансы 0!")
show_result(conn.execute("SELECT * FROM clients").fetchall())
"""))

    cells.append(md("""\
        ## 3. Атака через подбор: WHERE 1=1 (маскировка)

        Иногда разработчик «забывает» предикат, иногда — пишет «всегда истинное»
        условие (`WHERE 1=1`, `WHERE true`, `WHERE created_at < now()`).
        Эффект тот же — обнуление всех строк.
        """))

    cells.append(code("""\
# Восстановим таблицу
conn = setup_clients_db()


##
# @brief УЯЗВИМАЯ функция с замаскированным «всегда истинным» предикатом.
def zero_balance_BAD_MASKED(conn, client_id: int):
    sql = "UPDATE clients SET balance = 0 WHERE 1 = 1"  # ← синтаксически WHERE есть
    print(f"  Выполняется: {sql}")
    conn.execute(sql)
    conn.commit()


zero_balance_BAD_MASKED(conn, 3)
section("Состояние после маскировки — снова всё нулём")
show_result(conn.execute("SELECT * FROM clients").fetchall())
"""))

    cells.append(md("""\
        ## 4. Аудитор Phase 1 — правила R002 / R003

        В проде:
        ```python
        class UpdateNoWhere(Visitor):
            def visit_UpdateStmt(self, ancestors, node):
                if node.whereClause is None:
                    yield Finding("R002-update-no-where", risk_score=9)
                elif is_always_true(node.whereClause):
                    yield Finding("R002-update-no-where", risk_score=9, note="маскировка")
        ```

        Здесь — regex-эквивалент.
        """))

    cells.append(code("""\
##
# @brief Phase 1: ищет UPDATE/DELETE без WHERE или с always-true.
def audit_R002_R003(sql_text):
    findings = []
    is_update = bool(re.match(r"\\s*UPDATE\\b", sql_text, re.IGNORECASE))
    is_delete = bool(re.match(r"\\s*DELETE\\b", sql_text, re.IGNORECASE))
    if not (is_update or is_delete):
        return findings

    where_clause = re.search(r"\\bWHERE\\b(.*?)(?:RETURNING|;|$)", sql_text,
                             re.IGNORECASE | re.DOTALL)

    if where_clause is None:
        # WHERE отсутствует
        findings.append({
            "rule_id":       "R002-update-no-where" if is_update else "R003-delete-no-where",
            "vuln_class":    "DML_NO_WHERE",
            "severity":      "high", "risk_score": 9,
            "message":       f"{'UPDATE' if is_update else 'DELETE'} без WHERE — затрагивает все строки",
            "evidence_refs": ["CWE-1284"],
        })
    else:
        wc = where_clause.group(1).strip().rstrip(";").strip()
        always_true_patterns = [
            r"^\\s*1\\s*=\\s*1\\s*$",
            r"^\\s*TRUE\\s*$",
            r"^\\s*'[^']*'\\s*=\\s*'\\\\1\\\\1'\\s*$",  # 'x'='x'
        ]
        if any(re.match(p, wc, re.IGNORECASE) for p in always_true_patterns):
            findings.append({
                "rule_id":       "R002-update-no-where" if is_update else "R003-delete-no-where",
                "vuln_class":    "DML_NO_WHERE",
                "severity":      "high", "risk_score": 9,
                "message":       f"WHERE {wc!r} — всегда истинно (маскировка)",
                "evidence_refs": ["CWE-1284"],
            })
    return findings


section("Аудитор по 3 запросам")
for sql in [
    "UPDATE clients SET balance = 0",
    "UPDATE clients SET balance = 0 WHERE 1 = 1",
    "UPDATE clients SET balance = 0 WHERE client_id = ?",  # это безопасный — должно быть тихо
]:
    print(f"\\n SQL: {sql}")
    fs = audit_R002_R003(sql)
    if fs:
        for f in fs:
            print_finding(f)
    else:
        print("  ✅ всё ок")
"""))

    cells.append(md("""\
        ## 5. Безопасная функция
        """))

    cells.append(code("""\
##
# @brief Безопасная функция: обязательный WHERE по primary key.
# @param client_id  ID конкретного клиента.
def zero_balance_GOOD(conn, client_id: int):
    sql = "UPDATE clients SET balance = 0 WHERE client_id = ?"
    print(f"  SQL: {sql}  | param: client_id = {client_id}")
    conn.execute(sql, (client_id,))
    conn.commit()


conn = setup_clients_db()
section("Безопасный вызов: обнулим клиента #3")
zero_balance_GOOD(conn, 3)
section("Состояние после")
show_result(conn.execute("SELECT * FROM clients").fetchall())
"""))

    cells.append(footer_cell("04-dml-no-where"))
    return cells


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 05 — Privilege Escalation через SECURITY DEFINER
# ════════════════════════════════════════════════════════════════════════════
def build_05() -> list:
    cells = []

    cells.append(md("""\
        # 05 — Privilege Escalation через `SECURITY DEFINER`

        > **`vuln_class`:** `PRIV_ESCALATE` · **Риск:** 8/10 · **CWE-269** · **CAPEC-470**

        Функция в PostgreSQL объявлена с атрибутом `SECURITY DEFINER` — она выполняется с правами **владельца функции**, а не вызывающего. Если у функции **не зафиксирован `search_path`**, атакующий может подсунуть свою таблицу/функцию в `pg_temp` и **выполнить код в роли владельца** (часто это `postgres` — суперюзер).
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        Представь, что папа разрешил тебе **с его карточки** покупать
        молоко в магазине у дома. Он подписал инструкцию: «купить молоко».
        Карточка работает только когда ты несёшь молоко.

        Хитрый братик переклеивает в магазине ценники: на пачке жвачки
        пишет «молоко». Ты приходишь, кладёшь жвачку, кассир видит надпись
        «молоко», списывает с папиной карты. Хотя ты унёс жвачку, а не молоко.

        В SQL: функция `SECURITY DEFINER` ходит в БД от имени владельца.
        Если внутри функции написано просто «возьми из таблицы `users`»,
        а атакующий ДО вызова **создал свою таблицу `users` в `pg_temp`** —
        функция возьмёт **подделку атакующего** (потому что `pg_temp`
        выше в `search_path`).
        """))

    cells.append(md("""\
        ## ⚠️ Дисклеймер

        SQLite не имеет `SECURITY DEFINER`, `SET search_path`, `pg_temp`.
        Эти концепции — **строго про PostgreSQL**. Здесь мы **симулируем**
        атаку через Python-обёртку: имитируем «search_path» как простой
        словарь, видим как подмена работает.

        Если хочешь воспроизвести атаку **на настоящем Postgres**, см. PG docs:
        https://www.postgresql.org/docs/current/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY
        """))

    cells.append(md("""\
        ## 1. Setup — имитация Postgres + SECURITY DEFINER функции
        """))

    cells.append(code(COMMON_PREAMBLE + """

##
# @brief Имитация PostgreSQL search_path.
# @details
#   В Postgres `search_path` — список схем, по которым ищется неквалифицированное
#   имя объекта. Дефолт: 'pg_temp, "$user", public'. То есть pg_temp ВПЕРЕДИ public.
#   Если атакующий создаст в pg_temp функцию users(), она «затмит» public.users.
SEARCH_PATH = ["pg_temp", "public"]

# Имитация двух схем
SCHEMAS = {
    "public": {
        "users": [
            (1, "alice", "admin"),
            (2, "bob",   "user"),
        ],
    },
    "pg_temp": {},  # сюда атакующий может «положить» свою таблицу
}


def resolve_table(name):
    \"\"\"@brief Имитация PG: ищет таблицу по search_path.\"\"\"
    for schema in SEARCH_PATH:
        if name in SCHEMAS[schema]:
            return schema, SCHEMAS[schema][name]
    raise KeyError(f"таблица {name} не найдена")


print("Имитация PG: SEARCH_PATH =", SEARCH_PATH)
print("Содержимое public.users:")
show_result(SCHEMAS["public"]["users"])
"""))

    cells.append(md("""\
        ## 2. Уязвимая `SECURITY DEFINER` функция — без `SET search_path`
        """))

    cells.append(code("""\
##
# @brief УЯЗВИМАЯ функция: SECURITY DEFINER без SET search_path.
# @details
#   Имитируем поведение PG:
#     CREATE FUNCTION admin_lookup(login text) RETURNS bigint
#       LANGUAGE plpgsql SECURITY DEFINER  -- ⚠️ нет SET search_path
#     AS $$ SELECT id FROM users WHERE login = $1 $$;
# @warning  Берёт неквалифицированное имя `users` — может попасть в pg_temp.
def admin_lookup_BAD(login):
    schema, table = resolve_table("users")
    print(f"  Функция читает users из схемы '{schema}' (search_path выбор)")
    for row in table:
        if row[1] == login:
            return row
    return None


section("Нормальный вызов: ищем alice")
print("  Результат:", admin_lookup_BAD("alice"))
"""))

    cells.append(md("""\
        ## 3. Атака: search_path hijacking
        """))

    cells.append(code("""\
section("АТАКА: атакующий кладёт свою таблицу users в pg_temp")
SCHEMAS["pg_temp"]["users"] = [
    (999, "alice", "admin"),     # имя как в public, но id=999 — поддельный
    (998, "fake_admin", "admin"),
]

section("Тот же вызов admin_lookup_BAD('alice')")
result = admin_lookup_BAD("alice")
print(f"  💀 Результат: {result}")
print(f"  💀 Функция вернула ПОДДЕЛЬНЫЕ данные из pg_temp,")
print(f"  💀 потому что pg_temp выше public в search_path.")
print(f"  💀 Если функция дальше что-то делает с этим id — выполнится с правами владельца.")
"""))

    cells.append(md("""\
        ## 4. Аудитор Phase 1 — правило R007

        Phase 1 в проде смотрит AST `CreateFunctionStmt` и проверяет:
        - есть ли атрибут `security definer`;
        - есть ли `SET search_path`.

        Здесь — regex по DDL-тексту.
        """))

    cells.append(code("""\
##
# @brief Phase 1 R007 — детект SECURITY DEFINER без SET search_path.
def audit_R007_security_definer(ddl_text):
    findings = []
    if not re.search(r"\\bSECURITY\\s+DEFINER\\b", ddl_text, re.IGNORECASE):
        return findings
    if not re.search(r"\\bSET\\s+search_path\\s*=", ddl_text, re.IGNORECASE):
        findings.append({
            "rule_id":       "R007-security-definer-no-search-path",
            "vuln_class":    "PRIV_ESCALATE",
            "severity":      "high", "risk_score": 8,
            "message":       "SECURITY DEFINER без SET search_path — search_path hijack",
            "evidence_refs": ["CWE-269", "CAPEC-470", "PG-docs#sql-createfunction"],
        })
    return findings


bad_ddl = \"\"\"
CREATE OR REPLACE FUNCTION admin_lookup(login text) RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
AS $$ DECLARE r bigint; BEGIN SELECT id INTO r FROM users WHERE login=$1; RETURN r; END $$;
\"\"\"
good_ddl = \"\"\"
CREATE OR REPLACE FUNCTION admin_lookup(login text) RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$ DECLARE r bigint; BEGIN SELECT id INTO r FROM public.users WHERE login=$1; RETURN r; END $$;
\"\"\"

section("Аудитор по плохой версии")
for f in audit_R007_security_definer(bad_ddl):
    print_finding(f)

section("Аудитор по хорошей версии")
fs = audit_R007_security_definer(good_ddl)
if fs:
    for f in fs:
        print_finding(f)
else:
    print("  ✅ Уязвимостей не найдено.")
"""))

    cells.append(md("""\
        ## 5. Безопасная функция
        """))

    cells.append(code("""\
section("Безопасная DDL (только текст, мы не исполняем — SQLite не PG)")
print(good_ddl)

print()
print("Ключевые отличия:")
print("  1. SET search_path = pg_catalog, pg_temp — фиксируем порядок схем.")
print("  2. FROM public.users — квалифицированное имя, не оставляем resolver-у выбор.")
print("  3. (отдельно) REVOKE ALL ON FUNCTION ... FROM PUBLIC; GRANT EXECUTE TO app_role.")
"""))

    cells.append(footer_cell("05-privilege-escalation-execute"))
    return cells


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 06 — PL/pgSQL: небезопасный EXECUTE
# ════════════════════════════════════════════════════════════════════════════
def build_06() -> list:
    cells = []

    cells.append(md("""\
        # 06 — PL/pgSQL: небезопасный EXECUTE

        > **`vuln_class`:** `PLPGSQL_UNSAFE` · **Риск:** 9/10 · **CWE-89** · **CAPEC-66**
        > **Бонусный класс ТЗ (+10 баллов)** — см. [docs/adr/0010-plpgsql-bonus-path.md](../docs/adr/0010-plpgsql-bonus-path.md).

        Внутри хранимой функции PL/pgSQL **динамический SQL** собирается через **конкатенацию** (`||`) или `format()` с `%s` (вместо безопасного `%L`/`%I` или `USING`). Это **SQL Injection** внутри хранимки — особенно опасный, если функция `SECURITY DEFINER`.
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        Хранимая функция — это **робот** в БД, который умеет выполнять
        задания. У тебя есть запечатанный конверт с инструкцией:
        «иди к **полке X** и принеси книгу».

        - **Плохо:** «полку X» ты пишешь в инструкции **обычным
          фломастером поверх**. Кто-то может стереть и написать
          «иди к складу и принеси всё».
        - **Хорошо:** в инструкции есть **специальный пустой квадратик**
          для номера полки, и ты вставляешь туда **табличку с числом**.
          Стереть и переписать не получится — это другой формат.

        В PL/pgSQL «фломастер» — это `||` (склейка строк). «Табличка» —
        это `USING $1` или `format(..., %L, x)`.
        """))

    cells.append(md("""\
        ## ⚠️ Дисклеймер

        SQLite не понимает PL/pgSQL. Мы **симулируем** хранимую функцию
        Python-обёрткой, которая принимает «тело функции» как строку и
        внутри собирает SQL — точно как PL/pgSQL.
        """))

    cells.append(md("""\
        ## 1. Setup
        """))

    cells.append(code(COMMON_PREAMBLE + """

def setup_users():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, login TEXT, password TEXT)")
    conn.executemany(
        "INSERT INTO users (login, password) VALUES (?, ?)",
        [("admin", "Sup3rS3cr3t"), ("bob", "qwerty"), ("alice", "12345")],
    )
    conn.commit()
    return conn


conn = setup_users()
show_result(conn.execute("SELECT * FROM users").fetchall())
"""))

    cells.append(md("""\
        ## 2. Уязвимая «хранимка» — конкатенация в EXECUTE
        """))

    cells.append(code("""\
##
# @brief Имитация уязвимой PL/pgSQL функции:
#   CREATE FUNCTION find_user(login text) RETURNS SETOF users AS $$
#   BEGIN
#       RETURN QUERY EXECUTE 'SELECT * FROM users WHERE login = ''' || login || '''';
#   END $$ LANGUAGE plpgsql;
# @warning  Конкатенация → классический SQLi.
def find_user_BAD_concat(conn, login: str):
    # Внутри «хранимки» собираем SQL через ||
    dynamic_sql = "SELECT * FROM users WHERE login = '" + login + "'"
    print(f"  EXECUTE: {dynamic_sql}")
    return conn.execute(dynamic_sql).fetchall()


##
# @brief Имитация уязвимой PL/pgSQL функции через format() c %s:
#   RETURN QUERY EXECUTE format('SELECT * FROM users WHERE login = %s', login);
# @warning  %s — НЕ безопасно (это эквивалент ||). Безопасно — %L.
def find_user_BAD_format(conn, login: str):
    dynamic_sql = "SELECT * FROM users WHERE login = %s" % login  # 🚨 %s, не %L!
    print(f"  EXECUTE: {dynamic_sql}")
    return conn.execute(dynamic_sql).fetchall()


section("Нормальный вызов — login приходит без кавычек, БД ищет 'admin'")
show_result(find_user_BAD_concat(conn, "admin"))
"""))

    cells.append(md("""\
        ## 3. Атака — payload в параметре функции
        """))

    cells.append(code("""\
section("АТАКА на конкатенацию")
payload = "x' OR '1'='1"
print(f"  Атакующий: login = {payload!r}")
rows = find_user_BAD_concat(conn, payload)
print(f"  💀 {len(rows)} строк (всех пользователей с паролями):")
show_result(rows)
"""))

    cells.append(md("""\
        ## 4. Аудитор Phase 1 — правила R012, R013

        Phase 1 в проде использует `pglast.parse_plpgsql()` (это редкая
        возможность — `sqlglot` PL/pgSQL не парсит). Здесь — regex по DDL.
        """))

    cells.append(code("""\
##
# @brief R012 — конкатенация через || внутри EXECUTE.
def audit_R012_concat(plpgsql_text):
    if re.search(r"EXECUTE\\s+['\\\"].*?\\|\\|", plpgsql_text, re.IGNORECASE | re.DOTALL):
        return [{
            "rule_id":       "R012-plpgsql-execute-concat",
            "vuln_class":    "PLPGSQL_UNSAFE",
            "severity":      "high", "risk_score": 8,
            "message":       "EXECUTE с конкатенацией через || — SQL Injection",
            "evidence_refs": ["CWE-89", "CAPEC-66"],
        }]
    return []


##
# @brief R013 — format() с %s вместо %L/%I (или без USING).
def audit_R013_format_percent_s(plpgsql_text):
    if re.search(r"EXECUTE\\s+format\\s*\\(\\s*['\\\"].*?%s.*?['\\\"]",
                 plpgsql_text, re.IGNORECASE | re.DOTALL):
        return [{
            "rule_id":       "R013-plpgsql-format-without-using",
            "vuln_class":    "PLPGSQL_UNSAFE",
            "severity":      "high", "risk_score": 7,
            "message":       "format() с %s — эквивалент конкатенации, ожидается %L или USING",
            "evidence_refs": ["CWE-89"],
        }]
    return []


bad_plpgsql = \"\"\"
CREATE OR REPLACE FUNCTION find_user(login text)
RETURNS SETOF users LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY EXECUTE 'SELECT * FROM users WHERE login = ''' || login || '''';
END $$;
\"\"\"

bad_plpgsql_format = \"\"\"
CREATE OR REPLACE FUNCTION find_user(login text)
RETURNS SETOF users LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY EXECUTE format('SELECT * FROM users WHERE login = %s', login);
END $$;
\"\"\"

good_plpgsql = \"\"\"
CREATE OR REPLACE FUNCTION find_user(login text)
RETURNS SETOF users LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY EXECUTE 'SELECT * FROM users WHERE login = $1' USING login;
END $$;
\"\"\"

section("Аудитор: версия с ||")
for f in audit_R012_concat(bad_plpgsql):
    print_finding(f)

section("Аудитор: версия с format(%s)")
for f in audit_R013_format_percent_s(bad_plpgsql_format):
    print_finding(f)

section("Аудитор: безопасная версия (USING)")
fs = audit_R012_concat(good_plpgsql) + audit_R013_format_percent_s(good_plpgsql)
if fs:
    for f in fs:
        print_finding(f)
else:
    print("  ✅ Уязвимостей не найдено.")
"""))

    cells.append(md("""\
        ## 5. Безопасная версия
        """))

    cells.append(code("""\
print("Эталонный fix:")
print(good_plpgsql)
print()
print("Три безопасных способа динамического SQL в PL/pgSQL:")
print("  1. EXECUTE '... = $1' USING var       — параметризация")
print("  2. EXECUTE format('... = %L', var)    — для литералов")
print("  3. EXECUTE format('... %I ...', tbl)  — для идентификаторов")
print("  ❌ EXECUTE '...' || var               — НЕЛЬЗЯ")
print("  ❌ EXECUTE format('... = %s', var)    — НЕЛЬЗЯ (%s = ||)")
"""))

    cells.append(footer_cell("06-plpgsql-unsafe-execute"))
    return cells
