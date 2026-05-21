"""
@file seed_examples.py
@brief Seed-примеры датасета на РЕАЛЬНОЙ схеме заказчика (data_model.sql).

@details
    Это «посевной» набор — образец формата для команды (роль «Данные»).
    Цель — 300 примеров; здесь ~12 как шаблон по всем классам.

    Каждый пример:
      - safe        → только sql_good;
      - vulnerable  → sql_bad (как НЕ надо) + sql_good (как надо).

    Все SQL — на настоящих таблицах: credit_contract, acc_number,
    dict_product, ic_application, count_turnover, cb_interest_rate,
    business_segment, sys_object.

    Дополнять командой: добавляй SeedExample в SEED. build_dataset.py
    проверит метки и прогонит back-translation (SQL → NL).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from case3.dataset.models import SeedExample  # noqa: E402


SEED: list[SeedExample] = [

    # ─────────────────────────── SAFE (эталонные) ───────────────────────────
    SeedExample(
        id="ds-safe-001",
        intent="топ-100 кредитных договоров по сумме кредита, по убыванию",
        vuln_class="safe", difficulty="easy", tables=["credit_contract"],
        sql_good=(
            "SELECT id, credit_contract_number, credit_amount, loan_term "
            "FROM credit_contract "
            "WHERE status = 1 "
            "ORDER BY credit_amount DESC "
            "LIMIT 100"
        ),
    ),
    SeedExample(
        id="ds-safe-002",
        intent="сколько активных кредитных договоров в каждом подразделении",
        vuln_class="safe", difficulty="medium", tables=["credit_contract"],
        sql_good=(
            "SELECT org_id, COUNT(*) AS cnt "
            "FROM credit_contract "
            "WHERE status = 1 "
            "GROUP BY org_id "
            "ORDER BY cnt DESC"
        ),
    ),
    SeedExample(
        id="ds-safe-003",
        intent="дебетовый и кредитовый оборот по счёту за период",
        vuln_class="safe", difficulty="medium",
        tables=["count_turnover", "acc_number"],
        sql_good=(
            "SELECT a.account_name, ct.turnover_debit, ct.turnover_credit "
            "FROM count_turnover ct "
            "JOIN acc_number a ON a.id = ct.account_num_id "
            "WHERE ct.st_period >= '2026-01-01' "
            "ORDER BY ct.turnover_debit DESC "
            "LIMIT 500"
        ),
    ),

    # ─────────────────────────── SELECT_STAR ───────────────────────────
    SeedExample(
        id="ds-star-001",
        intent="показать кредитные договоры за последний месяц",
        vuln_class="SELECT_STAR", difficulty="easy", tables=["credit_contract"],
        sql_bad=(
            "SELECT * FROM credit_contract "
            "WHERE create_date > '2026-04-01' LIMIT 100"
        ),
        sql_good=(
            "SELECT id, credit_contract_number, credit_amount, create_date "
            "FROM credit_contract "
            "WHERE create_date > '2026-04-01' LIMIT 100"
        ),
        note="credit_contract имеет 76 колонок — SELECT * тащит всё, включая внутренние поля и FK-id.",
    ),

    # ─────────────────────────── DML_NO_WHERE ───────────────────────────
    SeedExample(
        id="ds-dml-001",
        intent="закрыть (status=0) кредитный договор с конкретным id",
        vuln_class="DML_NO_WHERE", difficulty="easy", tables=["credit_contract"],
        sql_bad="UPDATE credit_contract SET status = 0",
        sql_good="UPDATE credit_contract SET status = 0 WHERE id = $1",
        note="Без WHERE закроются ВСЕ договоры в банке.",
    ),
    SeedExample(
        id="ds-dml-002",
        intent="удалить черновую заявку ИУ по id",
        vuln_class="DML_NO_WHERE", difficulty="easy", tables=["ic_application"],
        sql_bad="DELETE FROM ic_application WHERE 1 = 1",
        sql_good="DELETE FROM ic_application WHERE id = $1 AND status = 0",
        note="WHERE 1=1 — маскировка отсутствия фильтра.",
    ),

    # ─────────────────────────── NO_PAGINATION / SLOW ───────────────────────────
    SeedExample(
        id="ds-limit-001",
        intent="выгрузить обороты по всем субконто",
        vuln_class="NO_PAGINATION", difficulty="easy", tables=["count_turnover"],
        sql_bad="SELECT id, account_num_id, turnover_debit, turnover_credit FROM count_turnover ORDER BY st_period DESC",
        sql_good="SELECT id, account_num_id, turnover_debit, turnover_credit FROM count_turnover ORDER BY st_period DESC LIMIT 1000",
        note="count_turnover — крупная таблица оборотов, без LIMIT вернёт миллионы строк.",
    ),
    SeedExample(
        id="ds-slow-001",
        intent="сопоставить договоры и обороты (забыт ON — декартово произведение)",
        vuln_class="SLOW_QUERY", difficulty="hard",
        tables=["credit_contract", "count_turnover"],
        sql_bad=(
            "SELECT cc.credit_contract_number, ct.turnover_debit "
            "FROM credit_contract cc, count_turnover ct LIMIT 1000"
        ),
        sql_good=(
            "SELECT cc.credit_contract_number, ct.turnover_debit "
            "FROM credit_contract cc "
            "JOIN count_turnover ct ON ct.account_num_id = cc.id LIMIT 1000"
        ),
        note="CROSS JOIN без условия = N×M строк; даже с LIMIT планировщик материализует декартово.",
    ),

    # ─────────────────────────── SQL_INJ_CLASSIC ───────────────────────────
    SeedExample(
        id="ds-sqli-001",
        intent="найти кредитный договор по номеру (номер вводит пользователь)",
        vuln_class="SQL_INJ_CLASSIC", difficulty="medium", tables=["credit_contract"],
        sql_bad=(
            "SELECT id, credit_amount FROM credit_contract "
            "WHERE credit_contract_number = '\" + user_input + \"'"
        ),
        sql_good=(
            "SELECT id, credit_amount FROM credit_contract "
            "WHERE credit_contract_number = $1"
        ),
        note="Конкатенация пользовательского ввода. Параметризация через $1.",
    ),

    # ─────────────────────────── SQL_INJ_UNION ───────────────────────────
    SeedExample(
        id="ds-union-001",
        intent="поиск продукта по названию (название от пользователя)",
        vuln_class="SQL_INJ_UNION", difficulty="hard", tables=["dict_product", "sys_object"],
        sql_bad=(
            "SELECT id, name FROM dict_product WHERE name LIKE '%x%' "
            "UNION SELECT id, name FROM sys_object --%'"
        ),
        sql_good="SELECT id, name FROM dict_product WHERE name LIKE $1",
        note="UNION дотягивается до sys_object (системные объекты).",
    ),

    # ─────────────────────────── SQL_INJ_TIME ───────────────────────────
    SeedExample(
        id="ds-time-001",
        intent="проверить существование договора по id (id от пользователя)",
        vuln_class="SQL_INJ_TIME", difficulty="hard", tables=["credit_contract"],
        sql_bad=(
            "SELECT id FROM credit_contract WHERE id = 1 "
            "OR (SELECT CASE WHEN (SELECT count(*) FROM credit_contract) > 0 "
            "THEN pg_sleep(3) ELSE pg_sleep(0) END)"
        ),
        sql_good="SELECT id FROM credit_contract WHERE id = $1",
        note="pg_sleep в CASE — time-based blind. Лечится параметризацией + statement_timeout.",
    ),

    # ─────────────────────────── PRIV_ESCALATE ───────────────────────────
    SeedExample(
        id="ds-priv-001",
        intent="функция-обёртка для чтения суммы кредита (admin-доступ)",
        vuln_class="PRIV_ESCALATE", difficulty="hard", tables=["credit_contract"],
        sql_bad=(
            "CREATE FUNCTION get_credit_amount(cid bigint) RETURNS numeric\n"
            "LANGUAGE plpgsql SECURITY DEFINER AS $$\n"
            "BEGIN RETURN (SELECT credit_amount FROM credit_contract WHERE id = cid); END $$"
        ),
        sql_good=(
            "CREATE FUNCTION get_credit_amount(cid bigint) RETURNS numeric\n"
            "LANGUAGE plpgsql SECURITY DEFINER\n"
            "SET search_path = pg_catalog, pg_temp AS $$\n"
            "BEGIN RETURN (SELECT credit_amount FROM public.credit_contract WHERE id = cid); END $$"
        ),
        note="SECURITY DEFINER без SET search_path — search_path hijack.",
    ),

    # ─────────────────────────── PLPGSQL_UNSAFE ───────────────────────────
    SeedExample(
        id="ds-plpgsql-001",
        intent="хранимая функция поиска договора по номеру",
        vuln_class="PLPGSQL_UNSAFE", difficulty="hard", tables=["credit_contract"],
        sql_bad=(
            "CREATE FUNCTION find_contract(num text) RETURNS SETOF credit_contract\n"
            "LANGUAGE plpgsql AS $$\nBEGIN\n"
            "  RETURN QUERY EXECUTE 'SELECT * FROM credit_contract WHERE credit_contract_number = ''' || num || '''';\n"
            "END $$"
        ),
        sql_good=(
            "CREATE FUNCTION find_contract(num text) RETURNS SETOF credit_contract\n"
            "LANGUAGE plpgsql AS $$\nBEGIN\n"
            "  RETURN QUERY EXECUTE 'SELECT * FROM credit_contract WHERE credit_contract_number = $1' USING num;\n"
            "END $$"
        ),
        note="EXECUTE с конкатенацией ||. Безопасно — через USING.",
    ),

    # ─────────────────────────── DIRECT_SENSITIVE ───────────────────────────
    # ВНИМАНИЕ: в схеме нет очевидных PII-колонок (password/passport).
    # Чувствительными для банка считаем финансовые суммы (credit_amount, обороты).
    # Список «sensitive» уточняется у заказчика (вопрос кураторам).
    SeedExample(
        id="ds-sensitive-001",
        intent="отчёт по суммам кредитов всех клиентов для выгрузки",
        vuln_class="DIRECT_SENSITIVE", difficulty="medium", tables=["credit_contract"],
        sql_bad="SELECT credit_contract_number, credit_amount, special_purpose FROM credit_contract LIMIT 1000",
        sql_good=(
            "SELECT org_id, COUNT(*) AS contracts, SUM(credit_amount) AS total "
            "FROM credit_contract GROUP BY org_id"
        ),
        note="Сырые суммы по каждому договору = коммерческая тайна. Безопасно — агрегат по подразделению. ТРЕБУЕТ уточнения списка sensitive у заказчика.",
    ),
]


if __name__ == "__main__":
    # Sanity-check при прямом запуске: валидация всех меток.
    safe = sum(1 for s in SEED if s.vuln_class == "safe")
    vuln = len(SEED) - safe
    by_class: dict[str, int] = {}
    for s in SEED:
        by_class[s.vuln_class] = by_class.get(s.vuln_class, 0) + 1
    print(f"Seed-примеров: {len(SEED)}  (safe={safe}, vulnerable={vuln})")
    print("По классам:")
    for vc, n in sorted(by_class.items()):
        print(f"  {vc:18s} {n}")
