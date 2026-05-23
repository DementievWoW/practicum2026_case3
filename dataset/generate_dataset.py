"""
@file generate_dataset.py
@brief Синтез большого датасета «NL → SQL» на РЕАЛЬНОЙ схеме заказчика.

@details
    Кейс GreenData: валидационного датасета «промпт → SQL → эталон» заказчик
    скорее всего не даст — его синтезируем сами (ментор: это даёт доп. баллы).

    Этот скрипт строит N записей (по умолчанию 500), читая schema_catalog.json,
    классифицируя колонки каждой таблицы по типам (id / fk / сумма / дата /
    текст / статус) и собирая из них валидный SQL по шаблонам.

    Состав (см. dataset/README.md и ADR-0006):
      - safe-записи        — эталон Execution Accuracy + few-shot генератора;
      - vulnerable-записи  — для Recall судьи, по всем 11 классам.

    Принцип «оба варианта»: у каждого уязвимого примера есть пара
    sql_bad / sql_good (тот же интент). В датасет пишутся ОБЕ версии:
      - sql_bad → запись с vuln_class=<класс>, is_vulnerable=True;
      - sql_good → запись vuln_class="safe", is_vulnerable=False (тот же seed_id).
    На sql_bad судья обязан поднять класс, на sql_good — молчать.

    Рукописные seed_examples.py подмешиваются как «якоря» (приоритетные
    кандидаты с выверенными формулировками), затем пул добивается шаблонами.

    Генерация ДЕТЕРМИНИРОВАННА (перечисление таблиц/колонок в фикс. порядке;
    random.Random(42) только для финального шаффла и train/eval-сплита).

    PII-находка: в основной схеме PII всё же ЕСТЬ — sys_employee.email/phone/
    birthday, sys_company.inn/contact_phone. Плюс синтетический overlay sim_*
    (sensitive_overlay.sql). Класс DIRECT_SENSITIVE строится на них.

    Запуск:
        python dataset/generate_dataset.py                 # 500 → data/dataset_v1.jsonl
        python dataset/generate_dataset.py --n 1000
        python dataset/generate_dataset.py --out data/dataset_v2.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from case3.dataset.models import DatasetRecord, VULN_CLASSES  # noqa: E402

SCHEMA_PATH = os.path.join(ROOT, "data", "schema_catalog.json")

# ─────────────────────────────────────────────────────────────────────────────
# Метаданные таблиц
# ─────────────────────────────────────────────────────────────────────────────

# Синтетический PII-overlay (sensitive_overlay.sql) — нет в schema_catalog.json,
# но создаётся в sandbox. Описываем колонки вручную, чтобы строить на них
# DIRECT_SENSITIVE и инъекции.
SIM_TABLES = [
    {
        "name": "sim_client", "comment": "Клиент-физлицо (заёмщик)",
        "columns": [
            {"name": "id", "type": "bigint NOT NULL", "comment": "ID"},
            {"name": "full_name", "type": "character varying(500)", "comment": "ФИО"},
            {"name": "passport", "type": "character varying(20)", "comment": "Паспорт"},
            {"name": "snils", "type": "character varying(14)", "comment": "СНИЛС"},
            {"name": "inn", "type": "character varying(12)", "comment": "ИНН физлица"},
            {"name": "phone", "type": "character varying(20)", "comment": "Телефон"},
            {"name": "email", "type": "character varying(200)", "comment": "Email"},
            {"name": "birth_date", "type": "date", "comment": "Дата рождения"},
            {"name": "address", "type": "character varying(1000)", "comment": "Адрес регистрации"},
        ],
    },
    {
        "name": "sim_payment_card", "comment": "Платёжная карта клиента",
        "columns": [
            {"name": "id", "type": "bigint NOT NULL", "comment": "ID"},
            {"name": "client_id", "type": "bigint", "comment": "Клиент"},
            {"name": "card_number", "type": "character varying(19)", "comment": "Номер карты"},
            {"name": "cvv", "type": "character varying(4)", "comment": "CVV код"},
            {"name": "expiry", "type": "character varying(7)", "comment": "Срок действия"},
            {"name": "pan", "type": "character varying(19)", "comment": "PAN"},
        ],
    },
    {
        "name": "sim_employee_account", "comment": "Учётная запись сотрудника",
        "columns": [
            {"name": "id", "type": "bigint NOT NULL", "comment": "ID"},
            {"name": "login", "type": "character varying(100)", "comment": "Логин"},
            {"name": "password_hash", "type": "character varying(256)", "comment": "Хеш пароля"},
            {"name": "api_token", "type": "character varying(256)", "comment": "API токен доступа"},
            {"name": "full_name", "type": "character varying(500)", "comment": "ФИО"},
            {"name": "phone", "type": "character varying(20)", "comment": "Телефон"},
        ],
    },
]

# Колонки, которые считаем чувствительными (PII / тайна / креды).
# Реальные — из основной схемы; sim_* — из overlay.
SENSITIVE_COLS = {
    "sys_employee": ["first_name", "second_name", "sur_name", "email", "phone", "birthday"],
    "sys_company": ["inn", "contact_phone", "attr_email"],
    "credit_contract": ["credit_amount", "special_purpose", "financial_position", "reserve_size"],
    "count_turnover": ["turnover_debit", "turnover_credit", "output_balance_debit"],
    "sim_client": ["full_name", "passport", "snils", "inn", "phone", "email", "birth_date", "address"],
    "sim_payment_card": ["card_number", "cvv", "expiry", "pan"],
    "sim_employee_account": ["login", "password_hash", "api_token", "phone"],
}

# Технические/служебные колонки — НЕ предлагаем как «интересные» для SELECT.
BORING = {
    "name__ru", "name__en", "is_system", "is_del", "is_check",
    "last_modified_user_id", "last_modified_emp_id", "last_modified_date",
    "created_emp_id",
}


@dataclass
class Table:
    """@brief Классифицированная таблица: какие колонки для чего годятся."""
    name: str
    label: str          # человекочитаемое имя сущности (из comment)
    cols: set[str]
    id_col: str | None
    name_col: str | None
    nums: list[str]     # numeric — суммы/обороты/ставки
    dates: list[str]    # timestamp/date
    texts: list[str]    # «интересные» varchar (не служебные)
    fks: list[str]      # bigint *_id / link_* / attr_* — ключи группировки
    comments: dict[str, str]
    has_status: bool

    def col_h(self, col: str) -> str:
        """@brief Человеческая подпись колонки (из comment, иначе имя)."""
        c = (self.comments.get(col) or "").strip()
        c = c.split("(")[0].split(",")[0].replace("\n", " ").strip()
        return c if c else col


def clean_label(comment: str, name: str) -> str:
    """@brief Чистое имя сущности из comment: убираем префиксы СКП./ОСВ:/Справочник:."""
    c = (comment or "").strip()
    for pref in ("СКП. ", "СКП.", "ОСВ: ", "ОСВ:", "АФХД. ", "АФХД.", "УАиГ. ", "УАиГ.",
                 "Справочник: ", "Справочник:", "СИНТЕТИКА: ", "РМ. ", "МЮЭР. ", "ИУ. ", "КТ. "):
        if c.startswith(pref):
            c = c[len(pref):].strip()
    c = c.split("{")[0].split(",")[0].split("(")[0].replace("\n", " ").strip()
    return c if c else name


def classify(raw: dict) -> Table:
    """@brief Разложить колонки таблицы по категориям для шаблонов."""
    cols = [c["name"] for c in raw["columns"]]
    colset = set(cols)
    comments = {c["name"]: (c.get("comment") or "") for c in raw["columns"]}
    types = {c["name"]: c["type"] for c in raw["columns"]}

    nums, dates, texts, fks = [], [], [], []
    for c in raw["columns"]:
        n, t = c["name"], c["type"]
        if n == "id":
            continue
        if t.startswith("numeric"):
            nums.append(n)
        elif "timestamp" in t or t.startswith("date"):
            dates.append(n)
        elif t.startswith("character varying"):
            if n not in BORING:
                texts.append(n)
        elif t.startswith("bigint"):
            if n.endswith("_id") or n.startswith("link_") or n.startswith("attr_"):
                fks.append(n)

    # стабильные группировочные ключи в начало
    for pref in ("org_id", "type_id", "user_id"):
        if pref in fks:
            fks.remove(pref)
            fks.insert(0, pref)

    return Table(
        name=raw["name"],
        label=clean_label(raw.get("comment", ""), raw["name"]),
        cols=colset,
        id_col="id" if "id" in colset else None,
        name_col="name" if "name" in colset else (texts[0] if texts else None),
        nums=nums, dates=dates, texts=texts, fks=fks,
        comments=comments, has_status="status" in colset,
    )


def load_tables() -> list[Table]:
    """@brief Загрузить и классифицировать бизнес-таблицы (без ms_*-контейнеров)."""
    raw = json.load(open(SCHEMA_PATH, encoding="utf-8"))["tables"]
    out = []
    for t in raw:
        if t["name"].startswith("ms_"):       # MultiSelect-контейнеры (2 колонки) — мусор
            continue
        if len(t["columns"]) < 4:
            continue
        out.append(classify(t))
    for t in SIM_TABLES:
        out.append(classify(t))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Пулы кандидатов
# ─────────────────────────────────────────────────────────────────────────────
# safe-кандидат:  (intent, sql, tables, difficulty)
# vuln-кандидат:  (intent, sql_bad, sql_good, tables, difficulty)

LIMITS = [50, 100, 200, 500, 1000]
PERIODS = [
    ("2026-01-01", "2026-04-01"),
    ("2025-01-01", "2026-01-01"),
    ("2026-04-01", "2026-05-01"),
    ("2024-01-01", "2025-01-01"),
]


def gen_safe(tables: list[Table]) -> list[tuple]:
    """
    @brief Шаблоны безопасных SELECT/агрегатов на реальных колонках.
    @details Кандидаты раскладываются round-robin (по одному шаблону с каждой
        таблицы), чтобы первые отобранные записи покрывали максимум таблиц.
    """
    per_table: list[list[tuple]] = []
    for i, t in enumerate(tables):
        out: list[tuple] = []
        n = LIMITS[i % len(LIMITS)]
        d_from, d_to = PERIODS[i % len(PERIODS)]
        nm = t.name_col
        where_st = "WHERE status = 1 " if t.has_status else ""

        # T1: топ-N по числовому полю
        if t.id_col and nm and t.nums:
            num = t.nums[i % len(t.nums)]
            out.append((
                f"топ-{n} записей «{t.label}» с наибольшим значением «{t.col_h(num)}»",
                f"SELECT id, {nm}, {num} FROM {t.name} {where_st}ORDER BY {num} DESC LIMIT {n}",
                [t.name], "easy",
            ))
        # T2: количество в разрезе ключа
        if t.fks:
            fk = t.fks[i % len(t.fks)]
            out.append((
                f"сколько записей «{t.label}» в разрезе «{t.col_h(fk)}»",
                f"SELECT {fk}, COUNT(*) AS cnt FROM {t.name} {where_st}GROUP BY {fk} ORDER BY cnt DESC LIMIT {n}",
                [t.name], "medium",
            ))
        # T3: сумма числового по ключу
        if t.fks and t.nums:
            fk = t.fks[i % len(t.fks)]
            num = t.nums[(i + 1) % len(t.nums)]
            out.append((
                f"суммарное «{t.col_h(num)}» по «{t.col_h(fk)}» в «{t.label}»",
                f"SELECT {fk}, SUM({num}) AS total, COUNT(*) AS cnt FROM {t.name} GROUP BY {fk} ORDER BY total DESC LIMIT {n}",
                [t.name], "medium",
            ))
        # T4: последние N по дате
        if t.id_col and nm and t.dates:
            dt = t.dates[i % len(t.dates)]
            out.append((
                f"последние {n} записей «{t.label}» по полю «{t.col_h(dt)}»",
                f"SELECT id, {nm}, {dt} FROM {t.name} ORDER BY {dt} DESC LIMIT {n}",
                [t.name], "easy",
            ))
        # T5: фильтр по периоду
        if t.id_col and nm and t.dates:
            dt = t.dates[(i + 1) % len(t.dates)]
            out.append((
                f"записи «{t.label}» за период по полю «{t.col_h(dt)}»",
                f"SELECT id, {nm}, {dt} FROM {t.name} WHERE {dt} >= '{d_from}' AND {dt} < '{d_to}' ORDER BY {dt} DESC LIMIT {n}",
                [t.name], "medium",
            ))
        # T6: поиск по идентификатору (параметризовано)
        if t.id_col and nm:
            extra = (", " + t.nums[0]) if t.nums else ""
            out.append((
                f"найти запись «{t.label}» по идентификатору",
                f"SELECT id, {nm}{extra} FROM {t.name} WHERE id = $1",
                [t.name], "easy",
            ))
        # T7: min/max/avg
        if t.nums:
            num = t.nums[i % len(t.nums)]
            out.append((
                f"минимум, максимум и среднее «{t.col_h(num)}» в «{t.label}»",
                f"SELECT MIN({num}) AS min_v, MAX({num}) AS max_v, AVG({num}) AS avg_v FROM {t.name} {where_st}".strip(),
                [t.name], "medium",
            ))
        # T8: уникальные значения ключа
        if t.fks:
            fk = t.fks[(i + 1) % len(t.fks)]
            out.append((
                f"уникальные значения «{t.col_h(fk)}» в «{t.label}»",
                f"SELECT DISTINCT {fk} FROM {t.name} {where_st}ORDER BY {fk} LIMIT {n}",
                [t.name], "easy",
            ))
        # T9: всего активных
        if t.has_status:
            out.append((
                f"сколько всего активных записей в «{t.label}»",
                f"SELECT COUNT(*) AS cnt FROM {t.name} WHERE status = 1",
                [t.name], "easy",
            ))
        per_table.append(out)

    # round-robin: сначала по 1-му шаблону каждой таблицы, потом по 2-му и т.д.
    from itertools import zip_longest
    interleaved: list[tuple] = []
    for row in zip_longest(*per_table):
        interleaved.extend(c for c in row if c is not None)
    return interleaved


def gen_select_star(t: Table, i: int) -> tuple | None:
    if not (t.id_col and t.name_col):
        return None
    n = LIMITS[i % len(LIMITS)]
    where_st = "WHERE status = 1 " if t.has_status else ""
    keep = [c for c in ["id", t.name_col] + t.nums[:1] + t.dates[:1] if c]
    good_cols = ", ".join(dict.fromkeys(keep))
    return (
        f"показать записи «{t.label}» (вернуть все поля)",
        f"SELECT * FROM {t.name} {where_st}LIMIT {n}",
        f"SELECT {good_cols} FROM {t.name} {where_st}LIMIT {n}",
        [t.name], "easy",
    )


def gen_dml_no_where(t: Table, i: int) -> tuple | None:
    if not (t.id_col and t.has_status):
        return None
    variants = [
        (f"UPDATE {t.name} SET status = 0",
         f"UPDATE {t.name} SET status = 0 WHERE id = $1"),
        (f"DELETE FROM {t.name}",
         f"DELETE FROM {t.name} WHERE id = $1"),
        (f"DELETE FROM {t.name} WHERE 1 = 1",
         f"DELETE FROM {t.name} WHERE id = $1 AND status = 0"),
        (f"UPDATE {t.name} SET status = 0 WHERE 1 = 1",
         f"UPDATE {t.name} SET status = 0 WHERE id = $1"),
    ]
    bad, good = variants[i % len(variants)]
    verb = "удалить" if bad.startswith("DELETE") else "закрыть (status=0)"
    return (
        f"{verb} запись «{t.label}» по идентификатору",
        bad, good, [t.name], "easy",
    )


def gen_no_pagination(t: Table, i: int) -> tuple | None:
    if not (t.id_col and t.name_col):
        return None
    order = (t.dates[0] if t.dates else "id")
    extra = (", " + t.nums[0]) if t.nums else ""
    n = LIMITS[i % len(LIMITS)]
    return (
        f"выгрузить все записи «{t.label}» (без ограничения)",
        f"SELECT id, {t.name_col}{extra} FROM {t.name} ORDER BY {order} DESC",
        f"SELECT id, {t.name_col}{extra} FROM {t.name} ORDER BY {order} DESC LIMIT {n}",
        [t.name], "easy",
    )


def gen_slow_query(t: Table, i: int) -> tuple | None:
    if not (t.id_col and t.texts):
        return None
    txt = t.texts[i % len(t.texts)]
    variants = [
        # leading wildcard — индекс не используется
        (f"поиск «{t.label}» по подстроке в «{t.col_h(txt)}»",
         f"SELECT id, {t.name_col} FROM {t.name} WHERE {txt} LIKE '%абв%' LIMIT 1000",
         f"SELECT id, {t.name_col} FROM {t.name} WHERE {txt} LIKE $1 LIMIT 1000"),
        # функция на колонке — sargability убита
        (f"найти «{t.label}» по «{t.col_h(txt)}» без учёта регистра",
         f"SELECT id, {t.name_col} FROM {t.name} WHERE LOWER({txt}) = 'абв' LIMIT 1000",
         f"SELECT id, {t.name_col} FROM {t.name} WHERE {txt} = $1 LIMIT 1000"),
        # большой OFFSET вместо keyset-пагинации
        (f"глубокая пагинация по «{t.label}»",
         f"SELECT id, {t.name_col} FROM {t.name} ORDER BY id OFFSET 100000 LIMIT 50",
         f"SELECT id, {t.name_col} FROM {t.name} WHERE id > $1 ORDER BY id LIMIT 50"),
    ]
    intent, bad, good = variants[i % len(variants)]
    return (intent, bad, good, [t.name], "hard")


def gen_sqli_classic(t: Table, i: int) -> tuple | None:
    if not (t.id_col and t.texts and t.name_col):
        return None
    txt = t.texts[i % len(t.texts)]
    return (
        f"найти «{t.label}» по «{t.col_h(txt)}» (значение вводит пользователь)",
        f"SELECT id, {t.name_col} FROM {t.name} WHERE {txt} = '\" + user_input + \"'",
        f"SELECT id, {t.name_col} FROM {t.name} WHERE {txt} = $1",
        [t.name], "medium",
    )


def gen_sqli_union(t: Table, i: int) -> tuple | None:
    if not (t.id_col and t.texts and t.name_col):
        return None
    txt = t.texts[i % len(t.texts)]
    return (
        f"поиск «{t.label}» по «{t.col_h(txt)}» (значение от пользователя)",
        f"SELECT id, {t.name_col} FROM {t.name} WHERE {txt} LIKE '%x%' "
        f"UNION SELECT id, name FROM sys_object --%'",
        f"SELECT id, {t.name_col} FROM {t.name} WHERE {txt} LIKE $1",
        [t.name, "sys_object"], "hard",
    )


def gen_sqli_time(t: Table, i: int) -> tuple | None:
    if not t.id_col:
        return None
    return (
        f"проверить существование записи «{t.label}» по id (id от пользователя)",
        f"SELECT id FROM {t.name} WHERE id = 1 "
        f"OR (SELECT CASE WHEN (SELECT count(*) FROM {t.name}) > 0 "
        f"THEN pg_sleep(3) ELSE pg_sleep(0) END)",
        f"SELECT id FROM {t.name} WHERE id = $1",
        [t.name], "hard",
    )


def gen_priv_escalate(t: Table, i: int) -> tuple | None:
    if not t.id_col:
        return None
    col = (t.nums[0] if t.nums else (t.texts[0] if t.texts else None))
    if not col:
        return None
    rettype = "numeric" if col in t.nums else "text"
    fn = f"get_{t.name}_{col}"[:60]
    bad = (
        f"CREATE FUNCTION {fn}(cid bigint) RETURNS {rettype}\n"
        f"LANGUAGE plpgsql SECURITY DEFINER AS $$\n"
        f"BEGIN RETURN (SELECT {col} FROM {t.name} WHERE id = cid); END $$"
    )
    good = (
        f"CREATE FUNCTION {fn}(cid bigint) RETURNS {rettype}\n"
        f"LANGUAGE plpgsql SECURITY DEFINER\n"
        f"SET search_path = pg_catalog, pg_temp AS $$\n"
        f"BEGIN RETURN (SELECT {col} FROM public.{t.name} WHERE id = cid); END $$"
    )
    return (
        f"функция-обёртка с admin-доступом для чтения «{t.col_h(col)}» из «{t.label}»",
        bad, good, [t.name], "hard",
    )


def gen_plpgsql_unsafe(t: Table, i: int) -> tuple | None:
    if not t.texts:
        return None
    txt = t.texts[i % len(t.texts)]
    fn = f"find_{t.name}"[:60]
    bad = (
        f"CREATE FUNCTION {fn}(p text) RETURNS SETOF {t.name}\n"
        f"LANGUAGE plpgsql AS $$\nBEGIN\n"
        f"  RETURN QUERY EXECUTE 'SELECT * FROM {t.name} WHERE {txt} = ''' || p || '''';\n"
        f"END $$"
    )
    good = (
        f"CREATE FUNCTION {fn}(p text) RETURNS SETOF {t.name}\n"
        f"LANGUAGE plpgsql AS $$\nBEGIN\n"
        f"  RETURN QUERY EXECUTE 'SELECT * FROM {t.name} WHERE {txt} = $1' USING p;\n"
        f"END $$"
    )
    return (
        f"хранимая функция поиска «{t.label}» по «{t.col_h(txt)}»",
        bad, good, [t.name], "hard",
    )


def _mask_expr(t: Table, col: str) -> str | None:
    """@brief Безопасное выражение для чувствительной колонки (маскирование/агрегат)."""
    h = t.col_h(col)
    if col in t.nums:
        return None  # числовые маскируем агрегатом отдельно
    low = col.lower()
    if "card_number" in low or low == "pan":
        return f"RIGHT({col}, 4) AS {col}_last4"
    if "cvv" in low or "password" in low or "token" in low or "snils" in low or "passport" in low:
        return None  # такие поля не отдаём вообще
    if "phone" in low:
        return f"LEFT({col}, 3) || '****' || RIGHT({col}, 2) AS {col}_masked"
    if "email" in low:
        return f"SUBSTRING({col} FROM 1 FOR 2) || '***@' AS {col}_masked"
    if "inn" in low:
        return f"RIGHT({col}, 4) AS {col}_last4"
    if "name" in low:
        return f"LEFT({col}, 1) || '.' AS {col}_initial"
    return f"'***' AS {col}_masked"


def gen_direct_sensitive(t: Table, i: int) -> list[tuple]:
    """@brief DIRECT_SENSITIVE на чувствительных таблицах; несколько комбинаций колонок."""
    sens = [c for c in SENSITIVE_COLS.get(t.name, []) if c in t.cols]
    if not sens:
        return []
    out: list[tuple] = []
    text_sens = [c for c in sens if c not in t.nums]
    num_sens = [c for c in sens if c in t.nums]

    diff = "easy" if t.name.startswith("sim_") else "medium"

    # — текстовые/PII: прямая выгрузка vs маскирование (окна по 2 колонки) —
    if text_sens:
        for start in range(0, max(1, len(text_sens)), 2):
            chunk = text_sens[start:start + 2] or text_sens[:2]
            bad_cols = ", ".join(chunk)
            masks = [m for m in (_mask_expr(t, c) for c in chunk) if m] or ["id"]
            good_cols = ", ".join(["id"] + masks)
            out.append((
                f"выгрузить из «{t.label}»: {', '.join(t.col_h(c) for c in chunk)}",
                f"SELECT {bad_cols} FROM {t.name} LIMIT 1000",
                f"SELECT {good_cols} FROM {t.name} LIMIT 1000",
                [t.name], diff,
            ))
        # точечный доступ по фильтру — фильтр НЕ снимает чувствительность
        if "id" in t.cols:
            chunk = text_sens[:2]
            bad_cols = ", ".join(chunk)
            masks = [m for m in (_mask_expr(t, c) for c in chunk) if m] or ["id"]
            out.append((
                f"карточка записи «{t.label}» с полями {', '.join(t.col_h(c) for c in chunk)}",
                f"SELECT {bad_cols} FROM {t.name} WHERE id = $1",
                f"SELECT {', '.join(['id'] + masks)} FROM {t.name} WHERE id = $1",
                [t.name], diff,
            ))
    # — числовые суммы: сырьё по строкам vs агрегат —
    if num_sens:
        num = num_sens[0]
        grp = t.fks[0] if t.fks else "type_id"
        if t.name_col:
            out.append((
                f"отчёт по «{t.col_h(num)}» из «{t.label}» (по каждой записи)",
                f"SELECT {t.name_col}, {num} FROM {t.name} LIMIT 1000",
                f"SELECT {grp}, SUM({num}) AS total, COUNT(*) AS cnt FROM {t.name} GROUP BY {grp}",
                [t.name], "medium",
            ))
    return out


# раскладка: класс → генератор (per-table)
PER_TABLE_GENERATORS = {
    "SELECT_STAR": gen_select_star,
    "DML_NO_WHERE": gen_dml_no_where,
    "NO_PAGINATION": gen_no_pagination,
    "SLOW_QUERY": gen_slow_query,
    "SQL_INJ_CLASSIC": gen_sqli_classic,
    "SQL_INJ_UNION": gen_sqli_union,
    "SQL_INJ_TIME": gen_sqli_time,
    "PRIV_ESCALATE": gen_priv_escalate,
    "PLPGSQL_UNSAFE": gen_plpgsql_unsafe,
}

# целевое число УЯЗВИМЫХ записей на класс (sql_bad). Сумма = 200.
VULN_TARGETS = {
    "SQL_INJ_CLASSIC": 22, "DML_NO_WHERE": 22, "SELECT_STAR": 22,
    "NO_PAGINATION": 22, "DIRECT_SENSITIVE": 22,
    "SQL_INJ_UNION": 18, "SQL_INJ_TIME": 18, "SLOW_QUERY": 18,
    "PRIV_ESCALATE": 18, "PLPGSQL_UNSAFE": 18,
}


def build_vuln_pools(tables: list[Table]) -> dict[str, list[tuple]]:
    """@brief Для каждого класса — список (intent, sql_bad, sql_good, tables, diff)."""
    pools: dict[str, list[tuple]] = {vc: [] for vc in VULN_TARGETS}
    for cls, fn in PER_TABLE_GENERATORS.items():
        for i, t in enumerate(tables):
            cand = fn(t, i)
            if cand:
                pools[cls].append(cand)
        # для DML/SLOW добиваем вторым проходом по другим вариантам
        if cls in ("DML_NO_WHERE", "SLOW_QUERY"):
            for i, t in enumerate(tables):
                cand = fn(t, i + 1)
                if cand:
                    pools[cls].append(cand)
    # DIRECT_SENSITIVE — генератор возвращает список
    for t in tables:
        pools["DIRECT_SENSITIVE"].extend(gen_direct_sensitive(t, 0))
    return pools


# ─────────────────────────────────────────────────────────────────────────────
# Подмешивание рукописных seed-якорей
# ─────────────────────────────────────────────────────────────────────────────
def seed_pools() -> tuple[list[tuple], dict[str, list[tuple]]]:
    """@brief Конвертирует seed_examples.SEED в приоритетные кандидаты."""
    try:
        from seed_examples import SEED
    except Exception:
        return [], {}
    safe: list[tuple] = []
    vuln: dict[str, list[tuple]] = {}
    for s in SEED:
        if s.vuln_class == "safe":
            safe.append((s.intent, s.sql_good, s.tables, s.difficulty))
        else:
            vuln.setdefault(s.vuln_class, []).append(
                (s.intent, s.sql_bad, s.sql_good, s.tables, s.difficulty)
            )
    return safe, vuln


# ─────────────────────────────────────────────────────────────────────────────
# Сборка записей
# ─────────────────────────────────────────────────────────────────────────────
def build_records(n_total: int) -> list[DatasetRecord]:
    tables = load_tables()
    seed_safe, seed_vuln = seed_pools()

    vuln_pools = build_vuln_pools(tables)
    safe_pool = gen_safe(tables)

    records: list[DatasetRecord] = []
    seen_sql: set[str] = set()
    counter: dict[str, int] = {}

    def add(seed_id: str, nl: str, sql: str, vc: str, vuln: bool,
            diff: str, tabs: list[str]) -> bool:
        key = " ".join(sql.split())
        if key in seen_sql:
            return False
        seen_sql.add(key)
        records.append(DatasetRecord(
            seed_id=seed_id, nl=nl, sql=sql, vuln_class=vc,
            is_vulnerable=vuln, difficulty=diff, tables=tabs,
        ))
        return True

    def sid(prefix: str) -> str:
        counter[prefix] = counter.get(prefix, 0) + 1
        return f"ds-{prefix}-{counter[prefix]:03d}"

    # — Уязвимые: seed-якоря первыми, затем шаблоны; каждая пара → 2 записи —
    # Пара атомарна: берём кандидата только если ОБЕ версии (bad и good) ещё
    # не встречались, чтобы у каждого уязвимого был свой парный safe-двойник.
    for cls, target in VULN_TARGETS.items():
        pool = seed_vuln.get(cls, []) + vuln_pools.get(cls, [])
        added = 0
        for (intent, bad, good, tabs, diff) in pool:
            if added >= target:
                break
            if " ".join(bad.split()) in seen_sql or " ".join(good.split()) in seen_sql:
                continue
            s = sid(cls.lower().replace("_", "-"))
            add(s, intent, bad, cls, True, diff, tabs)
            add(s, intent, good, "safe", False, diff, tabs)  # парный двойник
            added += 1

    # — Чистые safe — добиваем до n_total —
    for (intent, sql, tabs, diff) in seed_safe:
        if len(records) >= n_total:
            break
        add(sid("safe"), intent, sql, "safe", False, diff, tabs)
    for (intent, sql, tabs, diff) in safe_pool:
        if len(records) >= n_total:
            break
        add(sid("safe"), intent, sql, "safe", False, diff, tabs)

    return records[:n_total]


def split_records(records: list[DatasetRecord], eval_ratio: float = 0.2,
                  seed: int = 42) -> None:
    """@brief Стратифицированный train/eval по vuln_class (детерминированно)."""
    rng = random.Random(seed)
    by_class: dict[str, list[DatasetRecord]] = {}
    for r in records:
        by_class.setdefault(r.vuln_class, []).append(r)
    for items in by_class.values():
        rng.shuffle(items)
        n_eval = max(1, int(len(items) * eval_ratio))
        for i, r in enumerate(items):
            r.split = "eval" if i < n_eval else "train"


def main() -> None:
    ap = argparse.ArgumentParser(description="Синтез датасета NL→SQL (реальная схема)")
    ap.add_argument("--n", type=int, default=500, help="Сколько записей (по умолч. 500)")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "dataset_v1.jsonl"))
    args = ap.parse_args()

    records = build_records(args.n)
    split_records(records)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")

    # Отчёт
    n_vuln = sum(1 for r in records if r.is_vulnerable)
    n_train = sum(1 for r in records if r.split == "train")
    n_eval = sum(1 for r in records if r.split == "eval")
    by_class: dict[str, int] = {}
    for r in records:
        by_class[r.vuln_class] = by_class.get(r.vuln_class, 0) + 1

    print(f"Записей: {len(records)}  (train={n_train}, eval={n_eval})")
    print(f"  safe:        {len(records) - n_vuln}")
    print(f"  vulnerable:  {n_vuln}")
    print("\nПо классам:")
    for vc, c in sorted(by_class.items(), key=lambda x: (-x[1], x[0])):
        tag = "" if vc == "safe" or vc in VULN_CLASSES else "  ⚠ НЕИЗВЕСТНЫЙ"
        print(f"  {vc:18s} {c}{tag}")
    print(f"\nСохранено: {args.out}")


if __name__ == "__main__":
    main()
