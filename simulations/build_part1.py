"""
@file build_part1.py
@brief Ноутбуки 01, 02, 03 — семейство SQL Injection (classic, UNION, time-blind).
"""

from build_helpers import md, code, footer_cell, COMMON_PREAMBLE


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 01 — SQL Injection (классический)
# ════════════════════════════════════════════════════════════════════════════
def build_01() -> list:
    cells = []

    cells.append(md("""\
        # 01 — SQL Injection (классический)

        > **`vuln_class`:** `SQL_INJ_CLASSIC` · **Риск:** 10/10 · **CWE-89** · **CAPEC-66**

        ## Что мы покажем

        1. Сделаем мок-БД пользователей с паролями.
        2. Напишем **уязвимую** функцию логина — где ввод склеивается с SQL через `+`.
        3. Запустим **атаку** и увидим, как утекают данные.
        4. Покажем, как наш **аудитор Phase 1** ловит проблему.
        5. Напишем **безопасную** версию с параметризацией.
        6. Повторим ту же атаку — она уходит в пустоту.
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        У тебя есть копилка с замком и в ней лежат записки с именами друзей.
        Когда друг приходит, ты ищешь его записку.

        - **Плохой код** — это когда ты приклеиваешь имя друга прямо на дверь
          копилки и читаешь, что получилось. Если друг скажет
          `«Вася ИЛИ ВСЕ»`, ты прочитаешь именно `«Вася ИЛИ ВСЕ»` —
          и достанешь **ВСЕ** записки сразу.
        - **Хороший код** — у тебя есть отдельная картотека с именами.
          Сначала ищешь имя по картотеке, потом достаёшь нужную запись.
          Никакие хитрые слова не работают, потому что ты не «приклеиваешь»
          их к двери — ты ищешь по точному имени.

        SQL Injection — когда атакующий пишет в поле ввода логина не своё имя,
        а **дополнительный кусок SQL**, который БД честно выполняет.
        """))

    cells.append(md("""\
        ## 1. Setup — мок-БД пользователей

        Создаём in-memory SQLite. Никакого реального Postgres не нужно — нам
        важна **семантика SQL**, а она в SQLite такая же на нашем уровне.
        """))

    cells.append(code(COMMON_PREAMBLE + """

##
# @brief Создаёт мок-БД пользователей с 5 тестовыми записями.
# @return sqlite3.Connection с готовой таблицей `users`.
# @note
#   В реальной системе таблица берётся из data_model_sql/data_model.sql
#   и развёрнута в Docker-контейнере с миграциями Alembic.
def setup_users_db():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute(\"\"\"
        CREATE TABLE users (
            id            INTEGER PRIMARY KEY,
            login         TEXT NOT NULL,
            full_name     TEXT,
            password_hash TEXT,   -- В проде здесь HASH, тут plain для наглядности
            role          TEXT
        )
    \"\"\")
    cur.executemany(
        "INSERT INTO users (login, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
        [
            ("admin",   "Анна Админовна", "hash_5f8a_admin",  "admin"),
            ("ivanov",  "Иван Иванов",    "hash_2c4b_iv",     "user"),
            ("petrova", "Мария Петрова",  "hash_9d3e_pet",    "user"),
            ("smith",   "John Smith",     "hash_a1b2_smith",  "user"),
            ("test",    "Тест Тестов",    "hash_dead_test",   "user"),
        ],
    )
    conn.commit()
    return conn


conn = setup_users_db()
section("Что лежит в БД (всего у нас 5 пользователей)")
show_result(conn.execute("SELECT id, login, full_name, role FROM users").fetchall())
"""))

    cells.append(md("""\
        ## 2. Уязвимая функция логина

        Самый типичный антипаттерн — склейка ввода через f-string.
        Видишь `f"... = '{login}'"`? Это означает «что бы пользователь
        ни прислал, оно вставится в SQL ДОСЛОВНО».
        """))

    cells.append(code("""\
##
# @brief УЯЗВИМАЯ функция: ищет пользователя по логину через конкатенацию.
# @param login  Логин пользователя, пришёл от клиента.
# @return       Список найденных пользователей (login, full_name, role).
# @warning      SQL Injection через `||` и f-string!
# @details
#   Любой ввод подставляется в текст запроса дословно.
#   Если пользователь пришлёт `admin' OR '1'='1`, получится:
#       SELECT * FROM users WHERE login = 'admin' OR '1'='1'
#   и БД вернёт все строки.
def get_user_BAD(conn, login: str):
    # ⚠️ ЗДЕСЬ И ЕСТЬ УЯЗВИМОСТЬ — f-string + конкатенация
    sql = f"SELECT id, login, full_name, role FROM users WHERE login = '{login}'"
    print(f"  Сформированный SQL: {sql}")
    return conn.execute(sql).fetchall()


section("Нормальный сценарий — пользователь честно ввёл свой логин")
rows = get_user_BAD(conn, "ivanov")
print("  Результат:")
show_result(rows)
"""))

    cells.append(md("""\
        ## 3. Атака — пользователь вводит SQL вместо логина

        Атакующий вместо логина `ivanov` присылает специальную строку,
        которая «закрывает» исходную кавычку и добавляет условие
        `OR '1'='1'` — всегда истинное.
        """))

    cells.append(code("""\
section("АТАКА: payload вместо логина")
payload = "x' OR '1'='1"
print(f"  Атакующий прислал login = {payload!r}")
rows = get_user_BAD(conn, payload)
print(f"\\n  💀 Получено {len(rows)} строк (а должна быть 0 или 1):")
show_result(rows)


section("Усиленная атака: с UNION SELECT — попробуем достать пароли")
# Атакующий уже знает структуру (либо через первую атаку, либо по логам)
payload2 = "x' UNION SELECT id, login, password_hash, role FROM users --"
print(f"  payload = {payload2!r}")
rows = get_user_BAD(conn, payload2)
print(f"\\n  💀 Получено {len(rows)} строк, причём с password_hash:")
show_result(rows)
"""))

    cells.append(md("""\
        ## 4. Что только что произошло

        Мы передали в функцию **не логин, а часть SQL**. БД честно выполнила
        запрос целиком. В итоге атакующий:

        1. Получил **всех пользователей**, не зная ни одного логина.
        2. Через `UNION SELECT` достал **password_hash** для всех учёток.

        В реальной системе следующий шаг — попытка крекнуть hash и взять
        учётку администратора. Защита провалена.
        """))

    cells.append(md("""\
        ## 5. Аудитор Phase 1 — детектит проблему

        В реальной системе наш Phase 1 правило `R011-injection-marker`
        использует **`pglast`** (AST-парсинг). Здесь — упрощённый regex-чек
        для наглядности.

        Идея: ищем в коде функции **маркеры конкатенации** ввода в SQL —
        f-string с `{var}` внутри SQL-строки, `+ var +`, `.format(...)`,
        `% var`.
        """))

    cells.append(code("""\
import inspect

INJECTION_MARKERS = [
    (r"f[\\"\\'].*=\\s*[\\"\\']\\{", "f-string подставляет переменную внутрь кавычек"),
    (r"\\.execute\\(\\s*f[\\"\\']", ".execute(f'...{var}...') — конкатенация в SQL"),
    (r"\\.execute\\(\\s*[\\"\\'].*[\\"\\']\\s*\\+", ".execute('...' + var) — склейка через +"),
    (r"\\.execute\\(\\s*[\\"\\'].*[\\"\\'].*%\\s*\\w", "%-форматирование внутри execute"),
    (r"\\.execute\\(\\s*[\\"\\'].*\\{[^?]*\\}.*[\\"\\']", "format(...) подстановка в SQL"),
]


##
# @brief Упрощённый аудитор Phase 1 (правило R011).
# @details
#   В реальной системе обходим AST через pglast. Здесь — regex поверх
#   исходного кода функции. Берём src через inspect.getsource,
#   а если он недоступен (например, при exec без файла) — принимаем
#   текст функции аргументом.
# @param func_or_src  Python-функция ИЛИ её исходник как строка.
# @return             Список findings (или []).
def audit_phase1_classic_injection(func_or_src):
    if isinstance(func_or_src, str):
        src = func_or_src
    else:
        try:
            src = inspect.getsource(func_or_src)
        except (OSError, TypeError):
            src = repr(func_or_src)  # последний fallback
    findings = []
    for pattern, message in INJECTION_MARKERS:
        if re.search(pattern, src):
            findings.append({
                "rule_id":       "R011-injection-marker",
                "vuln_class":    "SQL_INJ_CLASSIC",
                "severity":      "high",
                "risk_score":    10,
                "message":       message,
                "evidence_refs": ["CWE-89", "CAPEC-66", "OWASP-SQLi-CS"],
            })
            break  # одного маркера достаточно
    return findings


section("Аудитор проверяет get_user_BAD")
for f in audit_phase1_classic_injection(get_user_BAD):
    print_finding(f)
"""))

    cells.append(md("""\
        ## 6. Безопасная функция — параметризация

        Та же логика, но через параметризацию. Драйвер `sqlite3` (как и
        `psycopg` для Postgres) сам подставит значение в подготовленный
        план — никакой текстовой склейки.
        """))

    cells.append(code("""\
##
# @brief Безопасная функция: ищет пользователя по логину через параметризацию.
# @param login  Логин (любой текст).
# @return       Список (id, login, full_name, role).
# @note
#   `?` — placeholder для параметра. Драйвер передаёт значение отдельно от
#   текста запроса. В psycopg для PostgreSQL placeholder — `%s`.
def get_user_GOOD(conn, login: str):
    sql = "SELECT id, login, full_name, role FROM users WHERE login = ?"
    print(f"  SQL (без интерполяции): {sql}")
    print(f"  Параметр (отдельно):    login = {login!r}")
    return conn.execute(sql, (login,)).fetchall()


section("Аудитор проверяет get_user_GOOD")
findings = audit_phase1_classic_injection(get_user_GOOD)
if findings:
    for f in findings:
        print_finding(f)
else:
    print("  ✅ Уязвимостей не найдено — аудитор одобрил функцию.")
"""))

    cells.append(md("""\
        ## 7. Та же атака на безопасную функцию

        Передаём тот же payload `x' OR '1'='1`. Сравним поведение.
        """))

    cells.append(code("""\
section("АТАКА на безопасную функцию")
payload = "x' OR '1'='1"
print(f"  Атакующий снова прислал login = {payload!r}")
rows = get_user_GOOD(conn, payload)
print(f"\\n  ✅ Получено {len(rows)} строк (драйвер искал пользователя с буквально таким логином):")
show_result(rows)


section("Атака с UNION тоже мимо")
payload2 = "x' UNION SELECT id, login, password_hash, role FROM users --"
rows = get_user_GOOD(conn, payload2)
print(f"  ✅ Получено {len(rows)} строк — атакующий ушёл с пустыми руками.")
"""))

    cells.append(footer_cell("01-sql-injection-classic"))
    return cells


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 02 — Union-based Injection
# ════════════════════════════════════════════════════════════════════════════
def build_02() -> list:
    cells = []

    cells.append(md("""\
        # 02 — Union-based SQL Injection

        > **`vuln_class`:** `SQL_INJ_UNION` · **Риск:** 9/10 · **CWE-89** · **CAPEC-66 (Union variant)**

        Это **вариант** SQL Injection, где атакующий через `UNION SELECT` к легитимному запросу присоединяет свой — и читает данные из таблиц, которые не были предусмотрены.
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        Представь, ты учительница и проверяешь домашки. Тебе сдают
        одну тетрадь — ты её читаешь и ставишь оценку.

        А теперь представь, что хитрый ученик **склеил скотчем** свою
        тетрадь и тетрадь соседа — и сдал тебе **двойную тетрадь**.
        Ты читаешь обе подряд, ставишь оценку — но видишь и чужие
        ответы тоже.

        UNION SELECT — это «скотч» в SQL. Атакующий **подклеивает второй
        запрос** к твоему и получает данные «соседней тетради» —
        например, таблицы с паролями.
        """))

    cells.append(md("""\
        ## 1. Setup — поиск по каталогу товаров + соседняя таблица auth.users

        У нас есть публичная таблица товаров и приватная таблица учёток.
        """))

    cells.append(code(COMMON_PREAMBLE + """

##
# @brief Создаёт две таблицы: products (публичная) и users (приватная).
def setup_shop_db():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute(\"\"\"
        CREATE TABLE products (
            id    INTEGER PRIMARY KEY,
            title TEXT,
            price REAL
        )\"\"\")
    cur.execute(\"\"\"
        CREATE TABLE users (
            id            INTEGER PRIMARY KEY,
            login         TEXT,
            password_hash TEXT
        )\"\"\")
    cur.executemany(
        "INSERT INTO products (title, price) VALUES (?, ?)",
        [("Молоток", 500), ("Гвозди", 50), ("Дрель", 5000), ("Шуруповёрт", 7000)],
    )
    cur.executemany(
        "INSERT INTO users (login, password_hash) VALUES (?, ?)",
        [
            ("admin",  "hash_super_secret_admin"),
            ("ceo",    "hash_super_secret_ceo"),
            ("intern", "hash_intern_qwerty"),
        ],
    )
    conn.commit()
    return conn


conn = setup_shop_db()
section("Публичный каталог товаров (видим в UI)")
show_result(conn.execute("SELECT id, title, price FROM products").fetchall())

section("Приватная таблица учёток (НИКОГДА не должна попасть в UI)")
show_result(conn.execute("SELECT id, login, password_hash FROM users").fetchall())
"""))

    cells.append(md("""\
        ## 2. Уязвимая функция поиска товара

        Типичный поиск по подстроке — без параметризации.
        """))

    cells.append(code("""\
##
# @brief УЯЗВИМАЯ функция поиска товара по части названия.
# @param q  Подстрока запроса от пользователя.
# @return   Список товаров (id, title).
# @warning  Конкатенация → возможен UNION-based injection.
def search_products_BAD(conn, q: str):
    sql = f"SELECT id, title FROM products WHERE title LIKE '%{q}%'"
    print(f"  SQL: {sql}")
    return conn.execute(sql).fetchall()


section("Нормальный поиск")
show_result(search_products_BAD(conn, "Дре"))
"""))

    cells.append(md("""\
        ## 3. Атака — поэтапная разведка через UNION

        Атакующий не знает заранее, сколько колонок возвращает запрос
        и какие у них типы. Подбирает шаг за шагом.
        """))

    cells.append(code("""\
section("ШАГ 1 атаки: подбираем число колонок")
# Если число колонок не сошлось — SQLite вернёт ошибку или 0 строк
for n in range(1, 5):
    payload = "x' UNION SELECT " + ", ".join(["NULL"] * n) + " --"
    try:
        rows = search_products_BAD(conn, payload)
        print(f"  Попытка {n} колонок: {len(rows)} строк ✓")
    except Exception as e:
        print(f"  Попытка {n} колонок: ОШИБКА — {e}")


section("ШАГ 2 атаки: подобрали число (2) — теперь крадём таблицу users")
payload = "x' UNION SELECT login, password_hash FROM users --"
print(f"  payload = {payload!r}")
rows = search_products_BAD(conn, payload)
print(f"\\n  💀 Получено {len(rows)} строк, и среди них — все пароли:")
show_result(rows)


section("ШАГ 3 атаки: ещё страшнее — узнаём, какие вообще есть таблицы")
payload = "x' UNION SELECT name, sql FROM sqlite_master --"
print(f"  payload = {payload!r}")
rows = search_products_BAD(conn, payload)
print(f"\\n  💀 Атакующий теперь знает всю схему БД:")
show_result(rows)
"""))

    cells.append(md("""\
        ## 4. Аудитор Phase 1 — правило R005-union-suspicious

        Используем `pglast` (в проде) или регулярки + AST (здесь — упрощённо).
        Сигналы для подозрения:

        1. `UNION` с **`NULL, NULL, NULL`** — probe-паттерн.
        2. `UNION` с обращением к системной таблице (`sqlite_master`, `information_schema`, `pg_catalog`).
        3. Рассинхрон числа колонок верх/низ (часто отлажен этап probe).
        4. UNION-подзапрос, который повторяет литерал из WHERE верхнего (mirror).
        """))

    cells.append(code("""\
import sqlite3 as _sql


SUSPICIOUS_TABLES = {"sqlite_master", "information_schema", "pg_catalog",
                     "pg_user", "pg_authid", "users", "credentials"}


##
# @brief Phase 1 правило R005 — детект подозрительного UNION.
# @details
#   Здесь, для наглядности, мы запускаем регулярки на тексте SQL,
#   который функция СФОРМИРОВАЛА. В проде — обходим AST после pglast.parse_sql,
#   проверяем SelectStmt.op == SETOP_UNION и его правую часть.
def audit_R005_union(sql_text: str):
    findings = []
    # 1. NULL-only probe
    if re.search(r"UNION\\s+(ALL\\s+)?SELECT\\s+(NULL\\s*,?\\s*)+(\\-\\-|$)",
                 sql_text, re.IGNORECASE):
        findings.append({
            "rule_id":       "R005-union-suspicious",
            "vuln_class":    "SQL_INJ_UNION",
            "severity":      "high", "risk_score": 8,
            "message":       "UNION SELECT NULL,NULL,... — probe-паттерн",
            "evidence_refs": ["CWE-89", "CAPEC-66"],
        })
    # 2. UNION с обращением к системной таблице
    m = re.search(r"UNION\\s+(?:ALL\\s+)?SELECT\\s+.*?FROM\\s+(\\w+)",
                  sql_text, re.IGNORECASE | re.DOTALL)
    if m and m.group(1).lower() in SUSPICIOUS_TABLES:
        findings.append({
            "rule_id":       "R005-union-suspicious",
            "vuln_class":    "SQL_INJ_UNION",
            "severity":      "high", "risk_score": 9,
            "message":       f"UNION SELECT ... FROM {m.group(1)} — доступ к чувствительной таблице",
            "evidence_refs": ["CWE-89", "CAPEC-66"],
        })
    return findings


section("Аудитор анализирует SQL, который слепили из payload-а")
malicious_sql = "SELECT id, title FROM products WHERE title LIKE '%x' UNION SELECT login, password_hash FROM users --%'"
for f in audit_R005_union(malicious_sql):
    print_finding(f)
"""))

    cells.append(md("""\
        ## 5. Безопасная функция — параметризация

        Тот же поиск, но через `?`. Что бы атакующий ни прислал — это
        будет строка, в которую LIKE поищет литерально.
        """))

    cells.append(code("""\
##
# @brief Безопасная функция: параметризация.
def search_products_GOOD(conn, q: str):
    sql = "SELECT id, title FROM products WHERE title LIKE ?"
    return conn.execute(sql, (f"%{q}%",)).fetchall()


section("АТАКА UNION на безопасную версию")
payload = "x' UNION SELECT login, password_hash FROM users --"
rows = search_products_GOOD(conn, payload)
print(f"  ✅ Получено {len(rows)} строк. Атакующий ищет товар, в названии которого буквально \\"{payload}\\" — таких нет.")
"""))

    cells.append(footer_cell("02-sql-injection-union"))
    return cells


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 03 — Time-based Blind SQL Injection
# ════════════════════════════════════════════════════════════════════════════
def build_03() -> list:
    cells = []

    cells.append(md("""\
        # 03 — Time-based Blind SQL Injection

        > **`vuln_class`:** `SQL_INJ_TIME` · **Риск:** 8/10 · **CWE-89** · **CAPEC-7 (Blind SQLi)**

        Атакующий **не видит ответ** запроса напрямую (например, API возвращает только 200/500). Зато он **управляет временем ответа** — `pg_sleep(N)` или тяжёлые вычисления внутри `CASE WHEN ...`.

        По задержке атакующий перебирает биты пароля.
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        Представь телефонный автомат, который **молчит** — но если ты
        наберёшь правильный номер, он **гудит дольше**, а если неправильный —
        гудит коротко. Ты не видишь ничего, кроме длины гудка. Но
        если ты будешь подбирать цифры одну за другой и смотреть,
        где гудок стал длиннее — ты узнаешь весь номер.

        В SQL: вместо «длинного гудка» — `pg_sleep(5)`. Вместо «правильной
        цифры» — правильный бит пароля. Это медленно, но **работает на
        тихом API, который даже не возвращает данные**.
        """))

    cells.append(md("""\
        ## 1. Setup — API на одну функцию `update_last_seen(uid)`

        Это типичный endpoint: «обнови время последнего захода пользователя».
        Возвращает только OK/ERROR — никаких данных.
        """))

    cells.append(code(COMMON_PREAMBLE + """

##
# @brief Создаёт мок-БД с двумя таблицами: users и last_seen.
def setup_users_lastseen_db():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, login TEXT, password TEXT)")
    cur.execute("CREATE TABLE last_seen (user_id INTEGER PRIMARY KEY, ts TEXT)")
    cur.executemany(
        "INSERT INTO users (login, password) VALUES (?, ?)",
        [("admin", "SuperSecret123"), ("ivanov", "qwerty"), ("petrova", "12345")],
    )
    conn.commit()
    return conn


##
# @brief Имитируем pg_sleep(N) — SQLite не имеет такой функции,
#        поэтому мы её эмулируем через time.sleep().
# @details
#   В реальном PostgreSQL `pg_sleep(N)` — это встроенная функция,
#   и её можно вызвать прямо из запроса:
#       SELECT pg_sleep(5) FROM ...
#   Здесь мы парсим SQL, ловим `pg_sleep(N)` и делаем time.sleep до
#   выполнения. Концептуально это даёт тот же эффект — задержку,
#   управляемую SQL-payload-ом.
def execute_with_pg_sleep_emulation(conn, sql):
    m = re.search(r"pg_sleep\\((\\d+(?:\\.\\d+)?)\\)", sql, re.IGNORECASE)
    delay = float(m.group(1)) if m else 0
    sql_clean = re.sub(r"pg_sleep\\([^)]*\\)", "1", sql, flags=re.IGNORECASE)
    if delay:
        time.sleep(min(delay, 2))  # обрезаем до 2 сек, чтобы ноутбук не висел
    return conn.execute(sql_clean).fetchall()


conn = setup_users_lastseen_db()
print("Setup готов — есть таблица users и last_seen.")
"""))

    cells.append(md("""\
        ## 2. Уязвимая функция

        Эндпоинт не возвращает данные — только OK. Атакующий не может
        вытянуть данные напрямую, но может… **дождаться задержки**.
        """))

    cells.append(code("""\
##
# @brief УЯЗВИМАЯ функция: обновляет last_seen, но конкатенирует uid.
# @param uid  ID пользователя (от клиента — текстом).
# @return     "ok" или "error", больше ничего.
# @warning    Time-based blind injection.
def update_last_seen_BAD(conn, uid: str):
    sql = f"UPDATE last_seen SET ts = datetime('now') WHERE user_id = {uid}"
    print(f"  SQL: {sql}")
    t0 = time.time()
    try:
        execute_with_pg_sleep_emulation(conn, sql)
        dt = time.time() - t0
        print(f"  Ответ: ok (время: {dt:.2f} сек)")
        return "ok", dt
    except Exception as e:
        print(f"  Ответ: error — {e}")
        return "error", 0


section("Нормальный вызов")
update_last_seen_BAD(conn, "1")
"""))

    cells.append(md("""\
        ## 3. Атака — boolean-exfiltration по времени

        Payload: `1 OR (CASE WHEN <условие> THEN pg_sleep(2) ELSE 0 END)`.

        Если условие истинно — задержка 2 сек. Иначе — мгновенно.
        Перебирая условие по битам, атакующий вытаскивает пароль.
        """))

    cells.append(code("""\
section("АТАКА: «угадываем первый символ пароля admin»")

# Атакующий не знает пароль. Перебирает по букве.
candidates = ["S", "P", "1", "q"]  # первая буква пароля
for c in candidates:
    payload = f"1 OR (CASE WHEN (SELECT password FROM users WHERE login='admin') LIKE '{c}%' THEN pg_sleep(2) ELSE 0 END)"
    print(f"\\n  Проверяем символ '{c}'...")
    _, dt = update_last_seen_BAD(conn, payload)
    if dt > 1.5:
        print(f"  💀 Задержка > 1.5 сек → первый символ пароля admin = '{c}'")
"""))

    cells.append(md("""\
        ## 4. Аудитор Phase 1 — `R006-pg-sleep`

        В проде через pglast обходим AST и ищем `FuncCall` с именами
        `pg_sleep`, `pg_sleep_for`, `pg_sleep_until`. Здесь — regex.
        """))

    cells.append(code("""\
##
# @brief Phase 1 правило R006 — детект pg_sleep в SQL.
def audit_R006_pg_sleep(sql_text):
    findings = []
    if re.search(r"\\bpg_sleep(_for|_until)?\\s*\\(", sql_text, re.IGNORECASE):
        # Если внутри CASE WHEN ... THEN pg_sleep — это классический blind
        is_case = bool(re.search(r"CASE\\s+WHEN.*?pg_sleep", sql_text,
                                 re.IGNORECASE | re.DOTALL))
        findings.append({
            "rule_id":       "R006-pg-sleep",
            "vuln_class":    "SQL_INJ_TIME",
            "severity":      "high", "risk_score": 9 if is_case else 8,
            "message":       "pg_sleep() в SQL — индикатор blind-injection"
                            + (" (внутри CASE — почти 100% blind exfil)" if is_case else ""),
            "evidence_refs": ["CWE-89", "CAPEC-7"],
        })
    return findings


section("Аудитор анализирует payload атакующего")
malicious = "UPDATE last_seen SET ts=datetime('now') WHERE user_id = 1 OR (CASE WHEN ... THEN pg_sleep(2) ELSE 0 END)"
for f in audit_R006_pg_sleep(malicious):
    print_finding(f)
"""))

    cells.append(md("""\
        ## 5. Безопасная версия

        Параметризация + ограничение `statement_timeout` на роли БД.
        """))

    cells.append(code("""\
##
# @brief Безопасная функция: параметризация + ожидаемый int.
# @note  В проде дополнительно: ALTER ROLE app SET statement_timeout = '5s'.
def update_last_seen_GOOD(conn, uid: int):
    sql = "UPDATE last_seen SET ts = datetime('now') WHERE user_id = ?"
    conn.execute(sql, (int(uid),))  # ← int() кастует, не-число выбросит ValueError
    return "ok"


section("АТАКА на безопасную версию")
payload = "1 OR pg_sleep(2)"
try:
    update_last_seen_GOOD(conn, payload)
except ValueError as e:
    print(f"  ✅ Безопасная версия отвергла ввод: {e}")
"""))

    cells.append(footer_cell("03-sql-injection-time-blind"))
    return cells
