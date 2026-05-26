#!/usr/bin/env python3.10
"""
@file ex_eval.py
@brief Execution Accuracy eval — главный критерий кейса (EX ≥ 70%, 15 баллов).

@details
    26 размеченных задач разной сложности на нашей seeded-БД (60 таблиц):
      A. агрегаты (12) — count/sum/min/max/group-by;
      B. сортировка+LIMIT (5) — top-N с детерминированным tie-break по id;
      C. join'ы (5) — настоящие FK (credit_contract↔sys_company/sys_employee/...);
      D. широкие таблицы (4) — scp_project_ans (120 кол), scp_application (104 кол).

    Сравнение: для top-N задач — упорядоченный список кортежей; для остальных —
    мультимножество (порядок не важен). Это корректный execution-based EX.

Запуск (требует .env с LLM_BASE_URL/API_KEY/MODEL):
    set -a; source .env; set +a
    PYTHONPATH=.:src python3.10 scripts/ex_eval.py
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter

sys.path[:0] = [os.path.join(os.getcwd(), "src"), os.getcwd()]
import psycopg2

from case3.schema.linker import SchemaLinker, _short_type
from case3.llm.factory import make_llm
from case3.nodes.generator import LLMGenerator

linker = SchemaLinker()

# (nl, gold_sql, [tables], ordered)
EVAL = [
    # ── A. агрегаты ────────────────────────────────────────────────────────
    ("Сколько всего кредитных договоров?",
     "SELECT count(*) FROM credit_contract", ["credit_contract"], False),
    ("Сколько кредитных договоров со статусом 1?",
     "SELECT count(*) FROM credit_contract WHERE status = 1", ["credit_contract"], False),
    ("Максимальная сумма кредита среди всех договоров",
     "SELECT max(credit_amount) FROM credit_contract", ["credit_contract"], False),
    ("Суммарная сумма всех кредитов",
     "SELECT sum(credit_amount) FROM credit_contract", ["credit_contract"], False),
    ("Сколько различных статусов у кредитных договоров",
     "SELECT count(DISTINCT status) FROM credit_contract", ["credit_contract"], False),
    ("Минимальный срок кредита (loan_term)",
     "SELECT min(loan_term) FROM credit_contract", ["credit_contract"], False),
    ("Сколько компаний в системе?",
     "SELECT count(*) FROM sys_company", ["sys_company"], False),
    ("Сколько компаний с заполненным ИНН",
     "SELECT count(*) FROM sys_company WHERE inn IS NOT NULL", ["sys_company"], False),
    ("Сколько всего сотрудников?",
     "SELECT count(*) FROM sys_employee", ["sys_employee"], False),
    ("Сколько сегментов бизнеса",
     "SELECT count(*) FROM business_segment", ["business_segment"], False),
    ("Количество договоров по каждому статусу",
     "SELECT status, count(*) FROM credit_contract GROUP BY status", ["credit_contract"], False),
    ("Сколько договоров с суммой кредита больше 500000",
     "SELECT count(*) FROM credit_contract WHERE credit_amount > 500000", ["credit_contract"], False),

    # ── B. сортировка + LIMIT (топ-N, детерминированный tie-break по id) ──
    ("Покажи первые 5 кредитных договоров по id: id и номер договора",
     "SELECT id, credit_contract_number FROM credit_contract ORDER BY id ASC LIMIT 5",
     ["credit_contract"], True),
    ("Первые 3 компании по id: id и name",
     "SELECT id, name FROM sys_company ORDER BY id ASC LIMIT 3",
     ["sys_company"], True),
    ("Первые 5 сегментов бизнеса (id, название) по id",
     "SELECT id, name FROM business_segment ORDER BY id ASC LIMIT 5",
     ["business_segment"], True),
    ("Топ-5 договоров по сумме кредита по убыванию (номер договора, сумма); при равенстве — по id ASC",
     "SELECT credit_contract_number, credit_amount FROM credit_contract "
     "ORDER BY credit_amount DESC, id ASC LIMIT 5",
     ["credit_contract"], True),
    ("Топ-3 самых ранних договоров (id, create_date) по дате создания ASC, затем по id ASC",
     "SELECT id, create_date FROM credit_contract "
     "ORDER BY create_date ASC, id ASC LIMIT 3",
     ["credit_contract"], True),

    # ── C. join'ы (настоящие FK) ──────────────────────────────────────────
    ("Имя компании-клиента для первых 5 договоров (по id договора). Колонки: cc.id, sc.name",
     "SELECT cc.id, sc.name FROM credit_contract cc "
     "JOIN sys_company sc ON cc.link_customer_id = sc.id "
     "ORDER BY cc.id ASC LIMIT 5",
     ["credit_contract", "sys_company"], True),
    ("Топ-5 компаний по числу договоров (count desc, name asc): name, count",
     "SELECT sc.name, count(*) FROM credit_contract cc "
     "JOIN sys_company sc ON cc.link_customer_id = sc.id "
     "GROUP BY sc.name ORDER BY count(*) DESC, sc.name ASC LIMIT 5",
     ["credit_contract", "sys_company"], True),
    ("Топ-5 сегментов бизнеса по числу компаний В них (INNER JOIN — сегменты без компаний не учитываем): bs.name, count",
     "SELECT bs.name, count(*) FROM sys_company sc "
     "JOIN business_segment bs ON sc.business_segment = bs.id "
     "GROUP BY bs.name ORDER BY count(*) DESC, bs.name ASC LIMIT 5",
     ["sys_company", "business_segment"], True),
    ("Имя сотрудника-владельца договора (используй колонку credit_contract.sys_employee_id), первые 5 договоров по id: cc.id, emp.name",
     "SELECT cc.id, e.name FROM credit_contract cc "
     "JOIN sys_employee e ON cc.sys_employee_id = e.id "
     "ORDER BY cc.id ASC LIMIT 5",
     ["credit_contract", "sys_employee"], True),
    ("Количество заявок по сегменту бизнеса напрямую (по полю scp_application.scp_business_segment), топ-5 по числу: segment name, count",
     "SELECT bs.name, count(*) FROM scp_application a "
     "JOIN business_segment bs ON a.scp_business_segment = bs.id "
     "GROUP BY bs.name ORDER BY count(*) DESC, bs.name ASC LIMIT 5",
     ["scp_application", "business_segment"], True),

    # ── D. широкие таблицы ────────────────────────────────────────────────
    ("Сколько всего проектов решений",
     "SELECT count(*) FROM scp_project_ans", ["scp_project_ans"], False),
    ("Топ-3 проектов решений по id: id и name",
     "SELECT id, name FROM scp_project_ans ORDER BY id ASC LIMIT 3",
     ["scp_project_ans"], True),
    ("Сколько заявок (scp_application)",
     "SELECT count(*) FROM scp_application", ["scp_application"], False),
    ("Топ-5 заявок по id: id и name",
     "SELECT id, name FROM scp_application ORDER BY id ASC LIMIT 5",
     ["scp_application"], True),
]

NOISE = {"name__ru", "name__en", "afr_ident", "afr_ord", "afr_note",
         "created_emp_id", "last_modified_emp_id", "last_modified_user_id", "last_modified_date"}
GENERIC = {"name", "id", "create date", ""}


def ddl_for(tables: list[str], max_cols: int = 20) -> str:
    """DAIL-стиль DDL: типы + значимые комментарии + FK-хинты."""
    out = []
    for n in tables:
        info = linker.tables.get(n)
        if not info:
            continue
        fks = {fk["column"]: (fk.get("ref_table"), fk.get("ref_column", "id"))
               for fk in info["fks"]}
        all_cols = [c for c in info["columns"] if c["name"] not in NOISE]
        # Естественный порядок + если FK-колонка обрезается max_cols — допишем в конец
        cols = list(all_cols[:max_cols])
        present = {c["name"] for c in cols}
        for c in all_cols:
            if c["name"] in fks and c["name"] not in present:
                cols.append(c)
        lines = []
        for c in cols:
            com = (c.get("comment") or "").strip()
            fk = fks.get(c["name"])
            fk_hint = f" FK:{fk[0]}.{fk[1]}" if fk else ""
            if com and com.lower() not in GENERIC:
                tail = f"  -- {com}{fk_hint}"
            elif fk_hint:
                tail = f"  -- {fk_hint.lstrip()}"
            else:
                tail = ""
            lines.append(f"  {c['name']} {_short_type(c['type'])},{tail}")
        out.append(f"CREATE TABLE {n} (  -- {info['comment']}\n" + "\n".join(lines) + "\n);")
    return "\n\n".join(out)


def run_sql(conn, sql: str, ordered: bool):
    cur = conn.cursor()
    try:
        cur.execute("SET statement_timeout='10s'")
        cur.execute(sql)
        rows = cur.fetchall()
        conn.rollback()
        return tuple(tuple(r) for r in rows) if ordered else Counter(tuple(r) for r in rows)
    except Exception:
        conn.rollback()
        return None
    finally:
        cur.close()


def main():
    llm = make_llm()
    conn = psycopg2.connect(host="localhost", port="5432", dbname="demo_db",
                            user="distr_user", password="pass")
    print(f"LLM: {llm.model if hasattr(llm,'model') else type(llm).__name__}")
    print(f"задач: {len(EVAL)}\n" + "=" * 86)
    cat_stat = {"A": [0, 0], "B": [0, 0], "C": [0, 0], "D": [0, 0]}
    ex = execu = 0
    lat = []
    for i, (nl, gold_sql, tbls, ordered) in enumerate(EVAL):
        cat = "A" if i < 12 else "B" if i < 17 else "C" if i < 22 else "D"
        cat_stat[cat][1] += 1
        gold = run_sql(conn, gold_sql, ordered)
        t0 = time.time()
        try:
            sql = LLMGenerator(llm=llm, db_schema=ddl_for(tbls)).generate(nl)
        except Exception:
            sql = ""
        lat.append(time.time() - t0)
        res = run_sql(conn, sql, ordered) if sql else None
        ok = "✅" if (res is not None and res == gold) else ("⚠️" if res is not None else "❌")
        if res is not None:
            execu += 1
        if res is not None and res == gold:
            ex += 1
            cat_stat[cat][0] += 1
        print(f"[{cat}] {ok} {nl[:55]:56} {lat[-1]:4.1f}s")
        if ok != "✅":
            print(f"        cand: {sql.replace(chr(10),' ')[:140]}")
            print(f"        gold: {gold_sql[:140]}")
    print("=" * 86)
    print(f"EX {ex}/{len(EVAL)} ({100*ex//len(EVAL)}%) | исполнимых {execu}/{len(EVAL)} | "
          f"сред. латентность {sum(lat)/len(lat):.1f}s")
    print(f"  A агрегаты:        {cat_stat['A'][0]}/{cat_stat['A'][1]}")
    print(f"  B ORDER BY+LIMIT:  {cat_stat['B'][0]}/{cat_stat['B'][1]}")
    print(f"  C join'ы (FK):     {cat_stat['C'][0]}/{cat_stat['C'][1]}")
    print(f"  D широкие таблицы: {cat_stat['D'][0]}/{cat_stat['D'][1]}")


if __name__ == "__main__":
    main()
