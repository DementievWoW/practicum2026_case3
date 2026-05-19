"""
@file build_part4.py
@brief Ноутбуки 10, 11, 12 — schema linking, reflection loop, synthetic dataset.
"""

from build_helpers import md, code, COMMON_PREAMBLE


def eng_footer(problem_dir: str):
    """@brief Финальные ссылки для engineering-ноутбуков."""
    return md(f"""\
        ## Итог

        Мы увидели проблему **под микроскопом** и **симуляцию решения** из ADR.

        ## Куда дальше

        - **Описание проблемы:** [problems/engineering/{problem_dir}/README.md](../problems/engineering/{problem_dir}/README.md)
        - **Варианты решения + почему так:** [problems/engineering/{problem_dir}/solutions.md](../problems/engineering/{problem_dir}/solutions.md)
        - **Архитектура цикла:** [docs/adr/0002-loop-architecture-langgraph.md](../docs/adr/0002-loop-architecture-langgraph.md)
        """)


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 10 — Schema linking на 60 таблицах
# ════════════════════════════════════════════════════════════════════════════
def build_10() -> list:
    cells = []

    cells.append(md("""\
        # 10 — Schema linking на 60 таблицах

        > **Инженерный вызов:** генератор не «видит» схему → галлюцинирует имена таблиц → EX падает до 30-40%.
        >
        > **Цель:** дать в промпт **только релевантные** таблицы (top-15 + FK-замыкание), не всю схему сразу.

        ## Что мы покажем

        1. Соберём мок-каталог из 60 таблиц (имитация `data_model_sql/data_model.sql`).
        2. Реализуем **bag-of-words эмбеддинг** через `Counter` (без внешних зависимостей).
        3. Найдём топ-15 таблиц по NL-вопросу через cosine similarity.
        4. Сделаем **замыкание по FK** — добавим справочники.
        5. Сравним: «вся схема в промпт» vs «только релевантные».
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        Ты пришёл в **огромную библиотеку** со 60 полками книг. Нужна
        книга про динозавров.

        - **Плохо:** взять **все 60 полок целиком** и тащить в комнату
          для чтения. Стол не вмещает, нужное теряется среди ненужного.
        - **Хорошо:** идёшь к **картотеке**, говоришь «динозавры», получаешь
          15 номеров полок. Идёшь именно туда. Полка про «эпоху мезозоя»
          ссылается на полку «карта мира того времени» — берёшь и её
          тоже (это **FK-замыкание**).

        Schema linking = картотека для БД.
        """))

    cells.append(md("""\
        ## 1. Setup — мок-каталог из 60 таблиц
        """))

    cells.append(code(COMMON_PREAMBLE + """

##
# @brief Мок-каталог из 60 таблиц банк/ERP домена.
# @details
#   В реальной системе мы читаем data_model_sql/data_model.sql и парсим
#   CREATE TABLE + COMMENT ON. Здесь — упрощённо: список туплов.
#   Поля: (имя, русский комментарий, [колонки], [FK к другим таблицам])
SCHEMA_CATALOG = [
    ("clients",          "Клиенты банка",                 ["client_id", "full_name", "passport", "phone", "balance"], []),
    ("acc_number",       "Номер счета клиента",           ["id", "client_id", "account_name", "type_id"], ["clients", "acc_type"]),
    ("acc_type",         "Тип счета (справочник)",        ["id", "name", "description"], []),
    ("credit_contract",  "Кредитный договор",             ["id", "client_id", "amount", "rate", "status_id"], ["clients", "credit_status"]),
    ("credit_status",    "Статус кредита (справочник)",   ["id", "name"], []),
    ("payment",          "Платёж по кредиту",             ["id", "contract_id", "amount", "date"], ["credit_contract"]),
    ("business_segment", "Бизнес-сегмент клиента",        ["id", "client_id", "segment_name"], ["clients"]),
    ("ic_application",   "Заявление на ипотеку",          ["id", "client_id", "amount", "created_at"], ["clients"]),
    ("mler_application", "Заявление на MLEr",             ["id", "client_id", "status"], ["clients"]),
    ("offices_psb",      "Офисы ПСБ",                     ["id", "name", "address", "city"], []),
    ("employees",        "Сотрудники банка",              ["id", "full_name", "office_id"], ["offices_psb"]),
    ("dict_product",     "Справочник банковских продуктов", ["id", "name", "type"], []),
    ("transaction_log",  "Журнал транзакций",             ["id", "account_id", "amount", "ts"], ["acc_number"]),
    ("cb_interest_rate", "Ставки ЦБ",                     ["id", "rate", "valid_from"], []),
    ("fs_file",          "Файлы-приложения",              ["id", "object_id", "path", "size"], []),
    ("count_turnover",   "Оборот по счёту",               ["id", "account_id", "month", "amount"], ["acc_number"]),
    ("participant_app",  "Заявление участника",           ["id", "client_id", "type"], ["clients"]),
    ("user_log",         "Журнал действий пользователей", ["id", "user_id", "action", "ts"], []),
    ("audit_event",      "Аудит-событие",                 ["id", "action", "user_id", "ts"], []),
    ("kpi_report",       "KPI-отчёт сотрудника",          ["id", "employee_id", "month", "value"], ["employees"]),
]
# Добавим ещё 40 «технических» таблиц вроде ms_<hash> с минимальным контекстом
for i in range(40):
    SCHEMA_CATALOG.append((f"ms_table_{i:03d}", f"Системная таблица №{i}", ["id", "name", "value"], []))

print(f"Всего таблиц в каталоге: {len(SCHEMA_CATALOG)}")
print(f"Первые 5:")
for t in SCHEMA_CATALOG[:5]:
    print(f"  {t[0]:20s}  {t[1]}")
"""))

    cells.append(md("""\
        ## 2. Bag-of-words эмбеддинг

        Реальная система использует `intfloat/multilingual-e5-large` —
        нейросеть, которая выдаёт 1024-мерный вектор по тексту.

        Здесь — **упрощённая версия** через `Counter`: считаем сколько
        раз каждое слово встречается в «описании» таблицы. Это
        достаточно для демо принципа.
        """))

    cells.append(code("""\
from collections import Counter
import math


##
# @brief Превращает текст в bag-of-words вектор.
# @param text  Любой текст (имя таблицы + комментарий + колонки).
# @return      Counter: слово → частота.
# @note  В проде вместо этого — sentence-transformers и FAISS.
def embed(text):
    # Приводим к нижнему регистру, разбиваем по не-буквам, убираем короткие
    words = re.findall(r"[a-zA-Zа-яА-Я]{3,}", text.lower())
    return Counter(words)


def table_text(table_tuple):
    name, comment, cols, fks = table_tuple
    return f"{name} {comment} {' '.join(cols)}"


##
# @brief Cosine similarity между двумя bag-of-words.
def cosine(a, b):
    common = set(a) & set(b)
    if not common:
        return 0.0
    num = sum(a[w] * b[w] for w in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    return num / (norm_a * norm_b) if norm_a and norm_b else 0.0


section("Эмбеддим все 60 таблиц")
table_vectors = [(t[0], embed(table_text(t))) for t in SCHEMA_CATALOG]
print(f"Вектор таблицы 'clients': {dict(list(table_vectors[0][1].items())[:5])} ... ({len(table_vectors[0][1])} слов)")
"""))

    cells.append(md("""\
        ## 3. Retrieval: top-15 по NL-вопросу

        Пользователь спрашивает по-русски, система ищет релевантные
        таблицы. Реальный пример из домена банка.
        """))

    cells.append(code("""\
##
# @brief Возвращает top-k таблиц по релевантности к вопросу.
def schema_link(question, k=15):
    q_vec = embed(question)
    scored = [(name, cosine(q_vec, vec)) for name, vec in table_vectors]
    scored.sort(key=lambda x: -x[1])
    return scored[:k]


section("Запрос: 'покажи мне всех клиентов с просроченными кредитами'")
top = schema_link("покажи мне всех клиентов с просроченными кредитами банка")
for name, score in top:
    print(f"  {score:.3f}  {name}")
"""))

    cells.append(md("""\
        ## 4. FK-замыкание

        Top-15 может содержать `credit_contract`, но **забыть** `clients`,
        потому что само слово «клиент» в каталоге `credit_contract` слабо
        представлено. FK-замыкание решает: если таблица A ссылается на B,
        обе нужны для JOIN.
        """))

    cells.append(code("""\
##
# @brief Расширяет топ таблицами, на которые они ссылаются по FK.
def fk_closure(selected_names):
    catalog_by_name = {t[0]: t for t in SCHEMA_CATALOG}
    result = set(selected_names)
    for name in list(result):
        if name not in catalog_by_name:
            continue
        for fk_target in catalog_by_name[name][3]:
            result.add(fk_target)
    return result


section("FK-замыкание для top-3")
top3 = [n for n, _ in top[:3]]
print(f"Top-3:                {top3}")
closed = fk_closure(top3)
print(f"После FK-замыкания:   {sorted(closed)}")
"""))

    cells.append(md("""\
        ## 5. Сравнение бюджета токенов
        """))

    cells.append(code("""\
def schema_to_prompt(table_names):
    \"\"\"Превращает список таблиц в DDL-фрагмент (грубая оценка токенов = символы/4).\"\"\"
    catalog_by_name = {t[0]: t for t in SCHEMA_CATALOG}
    out = []
    for name in table_names:
        if name not in catalog_by_name:
            continue
        _, comment, cols, _ = catalog_by_name[name]
        out.append(f"-- {name}: {comment}\\nCREATE TABLE {name} ({', '.join(cols)});")
    text = "\\n".join(out)
    tokens = len(text) // 4
    return text, tokens


section("ВАРИАНТ A: подать ВСЮ схему (60 таблиц)")
_, tok_all = schema_to_prompt([t[0] for t in SCHEMA_CATALOG])
print(f"  Токенов в промпте: ~{tok_all}")

section("ВАРИАНТ B: top-15 + FK-замыкание")
top15 = [n for n, _ in top]
final_set = sorted(fk_closure(top15))
_, tok_b = schema_to_prompt(final_set)
print(f"  Таблиц в промпте:  {len(final_set)}")
print(f"  Токенов в промпте: ~{tok_b}")
print(f"  Экономия:          {(1 - tok_b/tok_all) * 100:.0f}%")
"""))

    cells.append(md("""\
        ## 6. A/B-«симуляция» — что без schema linking сломалось бы

        Реально без schema linking генератор галлюцинировал бы имена
        таблиц. Мы это симулируем: «выдумываем» имена, которых нет.
        """))

    cells.append(code("""\
##
# @brief Mock-генератор: на 60 таблицах без schema linking — галлюцинирует.
def mock_generate_WITHOUT_linking(question, all_tables):
    # Симулируем: при бесконечном выборе модель путает имена
    return "SELECT * FROM client_overdue_credits  -- ⚠️ такой таблицы нет!"


##
# @brief Mock-генератор: со schema linking — использует только данные.
def mock_generate_WITH_linking(question, selected_tables):
    if "clients" in selected_tables and "credit_contract" in selected_tables:
        return \"\"\"SELECT c.full_name, cc.amount
FROM clients c
JOIN credit_contract cc ON cc.client_id = c.client_id
WHERE cc.status_id IN (SELECT id FROM credit_status WHERE name='overdue')\"\"\"
    return "SELECT * FROM clients  -- fallback"


section("БЕЗ schema linking — генератор галлюцинирует")
sql_bad = mock_generate_WITHOUT_linking("просроченные кредиты", [t[0] for t in SCHEMA_CATALOG])
print(f"  Сгенерировано: {sql_bad}")

section("СО schema linking — генератор знает, какие таблицы есть")
sql_good = mock_generate_WITH_linking("просроченные кредиты", final_set)
print(f"  Сгенерировано:")
for line in sql_good.split("\\n"):
    print(f"    {line}")
"""))

    cells.append(eng_footer("01-large-schema-linking"))
    return cells


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 11 — Reflection memory loop
# ════════════════════════════════════════════════════════════════════════════
def build_11() -> list:
    cells = []

    cells.append(md("""\
        # 11 — Reflection-память: цикл реально учится

        > **Главный исследовательский вопрос ТЗ:** как сделать так, чтобы
        > генератор учился на замечаниях судьи, а не повторял те же ошибки?
        >
        > **Решение:** между итерациями вставляем `reflector` — отдельный
        > узел, который переписывает findings в **компактные `Lesson`**, и
        > они подкладываются в системный промпт generator'а на следующей
        > итерации.

        ## Что мы покажем

        1. Mock-генератор: возвращает SQL по правилу «без reflection → повторяет ошибку».
        2. Mock-судья: упрощённый Phase 1 на 9 правилах из ADR-0004.
        3. Reflector: findings → `Lesson` (список 5 последних, deduped).
        4. Цикл `generator → judge → (reflector) → generator → ...` до 5 итераций.
        5. A/B: **с reflection vs без**. Видим, что без reflection цикл не сходится.
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        Ты решаешь контрольную по математике. Учитель проверяет, ставит
        тебе **галочки и крестики** на ошибки.

        - **Без reflection:** ты пересдаёшь и **снова делаешь те же ошибки**,
          потому что забыл что было не так. Учитель снова ставит крестики.
          Это бесконечно.
        - **С reflection:** перед пересдачей ты **записываешь
          в шпаргалку**: «не путать минус и плюс при переносе через =».
          Берёшь шпаргалку на пересдачу — больше эту ошибку не делаешь.

        В нашем цикле: shpargalka = `Lesson`. Reflector — это ты, кто
        пишет шпаргалку по галочкам учителя. Generator — снова пишущий
        контрольную, но теперь с шпаргалкой в руке.
        """))

    cells.append(md("""\
        ## 1. Setup — mock-генератор, mock-судья, состояние цикла
        """))

    cells.append(code(COMMON_PREAMBLE + """

from dataclasses import dataclass, field
from typing import Any


##
# @brief Имитация state-объекта LangGraph (см. ADR-0002).
@dataclass
class LoopState:
    task: str                              #!< NL-вопрос
    sql_history: list = field(default_factory=list)
    audit_history: list = field(default_factory=list)
    reflection: list = field(default_factory=list)  #!< последние Lesson-ы
    iteration: int = 0
    approved: bool = False
    final_sql: str = ""


##
# @brief Один lesson, который reflector кладёт в state.
@dataclass
class Lesson:
    rule_id: str
    lesson: str
    example_bad: str
    example_good: str

    def __str__(self):
        return f"[{self.rule_id}] {self.lesson}"


##
# @brief Mock-генератор. Эмулирует поведение Qwen-Coder.
# @param task         NL-вопрос.
# @param reflection   Накопленные lesson-ы из state.
# @return             SQL-строка.
# @details
#   Здесь мы симулируем «эволюцию ответа модели»:
#   - на iter 1 модель выдаёт SQL с тремя ошибками: SELECT *, без WHERE, без LIMIT;
#   - на каждой следующей итерации, если в reflection есть lesson по правилу,
#     модель «исправляет» соответствующую ошибку. Без reflection — повторяет.
def mock_generator(task, reflection):
    rules_to_fix = {l.rule_id for l in reflection}
    # Базовая «плохая» версия
    select_part = "id, full_name" if "DIRECT_SENSITIVE" in rules_to_fix or "SELECT_STAR" in rules_to_fix else "*"
    where_part = "WHERE balance > 0" if "DML_NO_WHERE" in rules_to_fix else ""
    limit_part = "LIMIT 100" if "NO_PAGINATION" in rules_to_fix else ""
    return f"SELECT {select_part} FROM clients {where_part} {limit_part}".strip()


section("Тест mock_generator: пустая reflection")
print(f"  iter1 SQL: {mock_generator('покажи клиентов', [])}")

section("Тест mock_generator: с lesson по SELECT_STAR")
lessons = [Lesson("SELECT_STAR", "не используй *", "SELECT * FROM ...", "SELECT id, full_name FROM ...")]
print(f"  iter2 SQL: {mock_generator('покажи клиентов', lessons)}")
"""))

    cells.append(md("""\
        ## 2. Mock-судья (Phase 1 правила)
        """))

    cells.append(code("""\
##
# @brief Mock-судья: симулирует Phase 1 правила.
def mock_judge(sql):
    findings = []
    if re.search(r"SELECT\\s+\\*", sql, re.IGNORECASE):
        findings.append({"rule_id": "SELECT_STAR", "risk_score": 5,
                         "message": "SELECT * — раскрывает все колонки"})
    if re.search(r"\\bDELETE\\b|\\bUPDATE\\b", sql, re.IGNORECASE) and \\
       not re.search(r"\\bWHERE\\b", sql, re.IGNORECASE):
        findings.append({"rule_id": "DML_NO_WHERE", "risk_score": 9,
                         "message": "UPDATE/DELETE без WHERE"})
    if re.match(r"\\s*SELECT", sql, re.IGNORECASE) and \\
       not re.search(r"\\bLIMIT\\b", sql, re.IGNORECASE) and \\
       not re.search(r"\\bCOUNT\\(", sql, re.IGNORECASE):
        findings.append({"rule_id": "NO_PAGINATION", "risk_score": 4,
                         "message": "SELECT без LIMIT"})
    overall = max((f["risk_score"] for f in findings), default=0)
    return {"findings": findings, "overall_risk": overall, "approved": overall < 4.0}


section("Тест mock_judge")
for sql in ["SELECT * FROM clients", "SELECT id FROM clients LIMIT 100", "DELETE FROM clients"]:
    r = mock_judge(sql)
    print(f"\\n SQL: {sql}")
    print(f"   approved: {r['approved']}, risk: {r['overall_risk']}")
    for f in r["findings"]:
        print(f"   - {f['rule_id']}: {f['message']}")
"""))

    cells.append(md("""\
        ## 3. Reflector — переписывает findings → Lesson
        """))

    cells.append(code("""\
##
# @brief Reflector: из findings формирует lesson-ы.
# @details
#   В реальной системе reflector — это Qwen-7B вызов с promptom.
#   Здесь — словарь «rule_id → готовый текст урока». Концептуально
#   то же самое: structured-output из судьи.
LESSON_TEMPLATES = {
    "SELECT_STAR": Lesson("SELECT_STAR",
                          "Не используй SELECT *, перечисляй колонки явно.",
                          "SELECT * FROM clients",
                          "SELECT id, full_name FROM clients"),
    "DML_NO_WHERE": Lesson("DML_NO_WHERE",
                           "UPDATE/DELETE всегда требует WHERE с predicate по PK.",
                           "UPDATE clients SET balance=0",
                           "UPDATE clients SET balance=0 WHERE client_id=$1"),
    "NO_PAGINATION": Lesson("NO_PAGINATION",
                            "Любой SELECT должен иметь LIMIT (или keyset pagination).",
                            "SELECT id FROM clients ORDER BY ts DESC",
                            "SELECT id FROM clients ORDER BY ts DESC LIMIT 100"),
    "DIRECT_SENSITIVE": Lesson("DIRECT_SENSITIVE",
                               "Чувствительные поля маскируй (LEFT, hash).",
                               "SELECT passport FROM clients",
                               "SELECT LEFT(passport, 4) || '******' FROM clients"),
}


def reflector(findings, prev_reflection):
    \"\"\"@brief Mock-reflector: lookup + дедуп.\"\"\"
    new_lessons = []
    for f in findings:
        if f["rule_id"] in LESSON_TEMPLATES:
            new_lessons.append(LESSON_TEMPLATES[f["rule_id"]])
    # Дедуп по rule_id, окно 5 последних
    combined = prev_reflection + new_lessons
    seen = {}
    for l in combined:
        seen[l.rule_id] = l
    return list(seen.values())[-5:]
"""))

    cells.append(md("""\
        ## 4. Полный цикл: generator → judge → reflector → loop
        """))

    cells.append(code("""\
##
# @brief Один полный прогон цикла генератор↔судья.
def run_loop(task, use_reflection, max_iter=5):
    state = LoopState(task=task)
    for it in range(1, max_iter + 1):
        state.iteration = it
        sql = mock_generator(state.task, state.reflection if use_reflection else [])
        state.sql_history.append(sql)
        audit = mock_judge(sql)
        state.audit_history.append(audit)
        if audit["approved"]:
            state.approved = True
            state.final_sql = sql
            return state
        # reflector — только если флаг включён
        if use_reflection:
            state.reflection = reflector(audit["findings"], state.reflection)
    state.final_sql = sql
    return state


def print_run(label, state):
    section(label)
    print(f"  approved:      {state.approved}")
    print(f"  iterations:    {state.iteration}")
    print(f"  final risk:    {state.audit_history[-1]['overall_risk']}")
    print(f"  reflection memory at end ({len(state.reflection)} lessons):")
    for l in state.reflection:
        print(f"    - {l}")
    print(f"  trajectory of risk:")
    for i, a in enumerate(state.audit_history, 1):
        print(f"    iter {i}: risk={a['overall_risk']}, findings={[f['rule_id'] for f in a['findings']]}")


section("A — БЕЗ reflection")
state_a = run_loop("покажи всех клиентов с балансом > 0", use_reflection=False)
print_run("Без reflection", state_a)

print()
section("B — С reflection")
state_b = run_loop("покажи всех клиентов с балансом > 0", use_reflection=True)
print_run("С reflection", state_b)
"""))

    cells.append(md("""\
        ## 5. Главная метрика — «% задач, где vuln_class repeats»

        Это **прямой ответ на исследовательский вопрос ТЗ**.
        """))

    cells.append(code("""\
def repeats_count(state):
    \"\"\"@brief Сколько раз одно и то же правило срабатывало дважды.\"\"\"
    seen = []
    repeats = 0
    for audit in state.audit_history:
        for f in audit["findings"]:
            if f["rule_id"] in seen:
                repeats += 1
            seen.append(f["rule_id"])
    return repeats


section("Сравнение метрик")
print(f"{'метрика':<28} {'без reflection':>18} {'с reflection':>18}")
print("-" * 64)
print(f"{'iterations_used':<28} {state_a.iteration:>18} {state_b.iteration:>18}")
print(f"{'approved':<28} {str(state_a.approved):>18} {str(state_b.approved):>18}")
print(f"{'final risk_score':<28} {state_a.audit_history[-1]['overall_risk']:>18} {state_b.audit_history[-1]['overall_risk']:>18}")
print(f"{'rules повторились':<28} {repeats_count(state_a):>18} {repeats_count(state_b):>18}")
"""))

    cells.append(eng_footer("02-reflection-memory-loop"))
    return cells


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 12 — Synthetic dataset (back-translation)
# ════════════════════════════════════════════════════════════════════════════
def build_12() -> list:
    cells = []

    cells.append(md("""\
        # 12 — Синтез датасета через back-translation (SQL → NL)

        > **Проблема:** валидационный датасет «NL → SQL → vuln_class» не
        > поставляется. Без него нечем мерить EX и Recall судьи.
        >
        > **Решение (ADR-0006):** берём SQL (свои + адаптации PortSwigger/sqlmap),
        > просим LLM сгенерировать **NL-формулировку** к каждому. NL генерируется
        > проще, чем SQL — это позволяет за пару долларов собрать домен-специфичный
        > eval-set.

        ## Что покажем

        1. Seed pool из 10 SQL (8 безопасных + 2 уязвимых).
        2. Mock-LLM `sql_to_text`: словарь шаблонов под SQL-паттерны.
        3. Валидация: pglast-парсинг, sandbox-исполнение, sanity check.
        4. Quality-gate: «Phase 1 должен подтвердить vuln_class».
        5. Train/eval split со стратификацией.
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        Учительница пишет **ответ задачи** (например, «42»). А потом
        нужно **придумать сам вопрос** так, чтобы ответ был 42:
        «сколько будет 6×7?», «сколько лет в полувеке?» и т.д.

        Это и есть **back-translation**: у нас есть готовый SQL (ответ),
        и LLM придумывает к нему вопрос на естественном языке.

        Это легче, чем обратное — генерировать SQL по вопросу (там надо
        знать схему и быть точным; вопросы же — гибкий язык).
        """))

    cells.append(md("""\
        ## 1. SQL seed pool
        """))

    cells.append(code(COMMON_PREAMBLE + """

##
# @brief Seed pool — 10 SQL, рукописных под нашу мок-схему.
SEED_SQL = [
    # safe (8)
    ("SELECT id, full_name, balance FROM clients WHERE balance > 0 ORDER BY balance DESC LIMIT 100",   "safe", "easy"),
    ("SELECT COUNT(*) FROM credit_contract WHERE status_id = 3",                                       "safe", "easy"),
    ("SELECT c.full_name, SUM(p.amount) FROM clients c JOIN payment p ON p.contract_id IN (SELECT id FROM credit_contract WHERE client_id=c.client_id) GROUP BY c.full_name LIMIT 50", "safe", "medium"),
    ("SELECT contract_id, MAX(date) FROM payment GROUP BY contract_id LIMIT 200",                      "safe", "medium"),
    ("SELECT segment_name, COUNT(*) FROM business_segment GROUP BY segment_name",                       "safe", "easy"),
    ("SELECT a.account_name, t.amount FROM acc_number a JOIN transaction_log t ON t.account_id=a.id WHERE t.ts > '2026-01-01' LIMIT 1000", "safe", "medium"),
    ("SELECT name FROM dict_product WHERE type='credit'",                                              "safe", "easy"),
    ("SELECT contract_id, amount FROM payment WHERE date BETWEEN '2026-01-01' AND '2026-04-01' LIMIT 500", "safe", "easy"),
    # vulnerable (2)
    ("DELETE FROM credit_contract",                                                                   "DML_NO_WHERE", "easy"),
    ("SELECT * FROM clients",                                                                         "SELECT_STAR", "easy"),
]

print(f"Seed pool: {len(SEED_SQL)} SQL")
for sql, vc, diff in SEED_SQL[:3]:
    print(f"  [{vc:14s}] [{diff:6s}] {sql[:60]}...")
"""))

    cells.append(md("""\
        ## 2. Mock-LLM: SQL → NL

        В реальной системе тут GPT-4o-mini или Qwen-Coder с промптом
        «опиши пошагово что делает SQL → сформулируй 2 NL-вопроса».
        Здесь — pattern-based mock на ключевых словах SQL.
        """))

    cells.append(code("""\
##
# @brief Mock-LLM: SQL → 2 NL-вопроса (short, long).
def mock_sql_to_text(sql):
    sql_lo = sql.lower()
    if "delete from" in sql_lo:
        m = re.search(r"delete from (\\w+)", sql_lo)
        tbl = m.group(1) if m else "таблицы"
        return {
            "nl_short": f"очисти таблицу {tbl}",
            "nl_long":  f"мне нужно полностью удалить все записи из {tbl}, это будет очистка",
        }
    if "count(*)" in sql_lo:
        m = re.search(r"from (\\w+)", sql_lo)
        tbl = m.group(1) if m else "таблицы"
        return {
            "nl_short": f"сколько строк в {tbl}",
            "nl_long":  f"посчитай, пожалуйста, сколько всего записей в {tbl} с учётом фильтра",
        }
    if "join" in sql_lo:
        return {
            "nl_short": "связь данных из нескольких таблиц",
            "nl_long":  "нужен отчёт, объединяющий информацию из разных таблиц по ключу",
        }
    if "select *" in sql_lo:
        m = re.search(r"from (\\w+)", sql_lo)
        tbl = m.group(1) if m else "таблицы"
        return {
            "nl_short": f"выгрузи всё из {tbl}",
            "nl_long":  f"экспортируй полностью все данные из таблицы {tbl} в csv",
        }
    if "group by" in sql_lo:
        return {
            "nl_short": "сгруппируй и подсчитай",
            "nl_long":  "сделай агрегацию по группам с подсчётом сумм/количеств",
        }
    return {
        "nl_short": "сделай выборку",
        "nl_long":  "вытащи данные согласно условиям",
    }


section("Тест back-translation на 3 примерах")
for sql, vc, diff in SEED_SQL[:3]:
    nl = mock_sql_to_text(sql)
    print(f"\\n  SQL:      {sql[:60]}")
    print(f"  vuln:     {vc}")
    print(f"  nl_short: {nl['nl_short']}")
    print(f"  nl_long:  {nl['nl_long']}")
"""))

    cells.append(md("""\
        ## 3. Валидация — pglast + sandbox-исполнение
        """))

    cells.append(code("""\
##
# @brief Sandbox: имитация Postgres через sqlite3 для проверки исполнимости SELECT.
def setup_sandbox():
    conn = sqlite3.connect(":memory:")
    # Минимальные таблицы для seed pool
    for ddl in [
        "CREATE TABLE clients (client_id INT, id INT, full_name TEXT, balance REAL)",
        "CREATE TABLE credit_contract (id INT, client_id INT, status_id INT, amount REAL)",
        "CREATE TABLE payment (id INT, contract_id INT, amount REAL, date TEXT)",
        "CREATE TABLE business_segment (id INT, client_id INT, segment_name TEXT)",
        "CREATE TABLE acc_number (id INT, account_name TEXT)",
        "CREATE TABLE transaction_log (id INT, account_id INT, amount REAL, ts TEXT)",
        "CREATE TABLE dict_product (id INT, name TEXT, type TEXT)",
    ]:
        conn.execute(ddl)
    # Сидинг 5 строк на таблицу
    for _ in range(5):
        conn.execute("INSERT INTO clients VALUES (?, ?, ?, ?)", (1, 1, "Иван", 100.0))
        conn.execute("INSERT INTO credit_contract VALUES (?, ?, ?, ?)", (1, 1, 3, 50000))
        conn.execute("INSERT INTO payment VALUES (?, ?, ?, ?)", (1, 1, 1000, "2026-02-15"))
        conn.execute("INSERT INTO business_segment VALUES (?, ?, ?)", (1, 1, "retail"))
        conn.execute("INSERT INTO acc_number VALUES (?, ?)", (1, "Расчётный"))
        conn.execute("INSERT INTO transaction_log VALUES (?, ?, ?, ?)", (1, 1, 50, "2026-02-15"))
        conn.execute("INSERT INTO dict_product VALUES (?, ?, ?)", (1, "Ипотека", "credit"))
    conn.commit()
    return conn


def validate(sql, conn):
    \"\"\"@brief Возвращает (ok, error_msg).\"\"\"
    # 1. Парсинг (в проде — pglast, тут — sqlite EXPLAIN)
    try:
        conn.execute(f"EXPLAIN {sql}")
    except sqlite3.Error as e:
        return False, f"parse error: {e}"
    # 2. Для SELECT — попробовать выполнить
    if sql.strip().upper().startswith("SELECT"):
        try:
            conn.execute(sql).fetchall()
        except sqlite3.Error as e:
            return False, f"runtime error: {e}"
    return True, ""


sandbox = setup_sandbox()
section("Валидация всех seed SQL")
for sql, vc, diff in SEED_SQL:
    ok, err = validate(sql, sandbox)
    status = "✅" if ok else "❌"
    print(f"  {status} [{vc:14s}] {sql[:50]}...  {err}")
"""))

    cells.append(md("""\
        ## 4. Quality-gate: Phase 1 должен подтвердить vuln_class
        """))

    cells.append(code("""\
def quality_check_vuln(sql, expected_vuln_class):
    \"\"\"@brief Проверяет, что Phase 1 правила подтверждают заявленный класс.\"\"\"
    if expected_vuln_class == "safe":
        # Не должно быть ни одного finding (упрощённо)
        return True
    # SELECT * → SELECT_STAR
    if expected_vuln_class == "SELECT_STAR":
        return bool(re.search(r"SELECT\\s+\\*", sql, re.IGNORECASE))
    if expected_vuln_class == "DML_NO_WHERE":
        return bool(re.search(r"^\\s*(DELETE|UPDATE)\\b(?!.*WHERE)", sql,
                              re.IGNORECASE | re.DOTALL))
    return False


section("Quality-gate: vuln_class согласован с правилами?")
for sql, vc, diff in SEED_SQL:
    ok = quality_check_vuln(sql, vc)
    print(f"  {'✅' if ok else '⚠️ '} [{vc:14s}] {sql[:50]}")
"""))

    cells.append(md("""\
        ## 5. Train/eval split со стратификацией
        """))

    cells.append(code("""\
import random


def stratified_split(samples, eval_ratio=0.2, seed=42):
    \"\"\"@brief Разбиваем по vuln_class сбалансированно.\"\"\"
    rng = random.Random(seed)
    by_class = {}
    for s in samples:
        by_class.setdefault(s[1], []).append(s)
    train, eval_ = [], []
    for vc, items in by_class.items():
        rng.shuffle(items)
        n_eval = max(1, int(len(items) * eval_ratio))
        eval_.extend(items[:n_eval])
        train.extend(items[n_eval:])
    return train, eval_


train, eval_set = stratified_split(SEED_SQL)
section("Split со стратификацией")
print(f"  train: {len(train)} примеров, eval: {len(eval_set)} примеров")
print(f"  по классам в eval:")
counts = {}
for s in eval_set:
    counts[s[1]] = counts.get(s[1], 0) + 1
for vc, n in counts.items():
    print(f"    {vc}: {n}")
"""))

    cells.append(eng_footer("03-synthetic-dataset"))
    return cells
