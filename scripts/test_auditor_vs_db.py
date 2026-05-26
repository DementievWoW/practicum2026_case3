#!/usr/bin/env python3.10
"""
Тестирование аудитора + проверка отклонённых запросов в реальной БД.

  1) прогоняем набор запросов (безопасные + уязвимые) через HybridAuditor;
  2) сверяем вердикт с ожиданием (accuracy / ложные срабатывания / пропуски);
  3) КАЖДЫЙ отклонённый запрос выполняем в Postgres, чтобы увидеть реальное
     поведение. DML/DDL — в транзакции с ROLLBACK (ничего не портим).

Запуск:  PYTHONPATH=.:src python3.10 scripts/test_auditor_vs_db.py
"""
import os
import sys
import time

sys.path[:0] = [os.path.join(os.getcwd(), "src"), os.getcwd()]
import psycopg2

from case3.nodes.auditor import HybridAuditor

CFG = dict(host="localhost", port="5432", dbname="demo_db", user="distr_user", password="pass")

# expect: 'safe' = должен быть одобрен, 'vuln' = должен быть отклонён
QUERIES = [
    ("safe", "SELECT id, name FROM business_segment WHERE id = 5 LIMIT 10"),
    ("safe", "SELECT credit_contract_number, loan_term FROM credit_contract WHERE id = 42 LIMIT 1"),
    ("safe", "SELECT count(*) FROM credit_contract"),
    ("vuln", "SELECT * FROM scp_project_ans LIMIT 10"),                       # SELECT_STAR
    ("vuln", "SELECT id, name FROM sys_company"),                             # NO_PAGINATION
    ("vuln", "SELECT credit_amount, check_account, bank_ident_number FROM credit_contract LIMIT 10"),  # DIRECT_SENSITIVE
    ("vuln", "SELECT inn, contact_phone, attr_email FROM sys_company LIMIT 10"),  # PII
    ("vuln", "UPDATE credit_contract SET status = 0"),                        # DML_NO_WHERE
    ("vuln", "DELETE FROM sys_employee"),                                     # DML_NO_WHERE
    ("vuln", "SELECT id FROM credit_contract WHERE credit_contract_number = '\" + user_input + \"'"),  # INJ_CLASSIC
    ("vuln", "SELECT id, name FROM business_segment UNION SELECT NULL, NULL"),  # UNION probe
    ("vuln", "SELECT credit_contract_number FROM credit_contract UNION SELECT table_name FROM information_schema.tables"),  # UNION exfil
    ("vuln", "SELECT id FROM credit_contract WHERE id = 1 AND pg_sleep(2) IS NULL"),  # TIME-based
    ("vuln", "SELECT id, name FROM sys_company WHERE name LIKE '%ООО%'"),     # SLOW (leading wildcard)
]


def first_word(sql):
    return sql.strip().split(None, 1)[0].upper()


def run_in_db(conn, sql):
    """Безопасно выполняем запрос и описываем реальное поведение."""
    kind = first_word(sql)
    cur = conn.cursor()
    try:
        if kind in ("SELECT", "WITH"):
            t0 = time.time()
            cur.execute(sql)
            rows = cur.fetchall()
            dt = time.time() - t0
            sample = " | ".join(str(x) for x in rows[0])[:90] if rows else "—"
            extra = f", время {dt:.1f}s" if dt >= 1 else ""
            conn.rollback()
            return f"вернул {len(rows)} строк{extra}; первая: {sample}"
        elif kind in ("UPDATE", "DELETE", "INSERT"):
            cur.execute("SET session_replication_role='replica';")  # снять FK для замера
            cur.execute(sql)
            n = cur.rowcount
            conn.rollback()  # НИЧЕГО не сохраняем
            return f"⚠️ затронул бы {n} строк (откатили)"
        else:  # DDL и пр.
            cur.execute(sql)
            conn.rollback()
            return "выполнился (DDL, откатили)"
    except Exception as e:
        conn.rollback()
        return f"ошибка БД: {str(e).splitlines()[0][:80]}"
    finally:
        cur.close()


def main():
    auditor = HybridAuditor()
    conn = psycopg2.connect(**CFG)

    tp = tn = fp = fn = 0
    print("=" * 100)
    for expect, sql in QUERIES:
        res = auditor.audit(sql)
        rejected = not res.approved
        classes = sorted({v.vuln_class for v in res.vulnerabilities})
        verdict = "ОТКЛОНЁН" if rejected else "ОДОБРЕН "
        # сверка с ожиданием
        if expect == "vuln" and rejected: tp += 1; mark = "✅"
        elif expect == "safe" and not rejected: tn += 1; mark = "✅"
        elif expect == "safe" and rejected: fp += 1; mark = "❌ЛОЖНОЕ"
        else: fn += 1; mark = "❌ПРОПУСК"

        print(f"\n[{expect.upper():4}] {sql[:80]}")
        print(f"   аудитор: {verdict} риск {res.overall_risk_score:.1f} {classes}  {mark}")
        if rejected:
            print(f"   в БД:    {run_in_db(conn, sql)}")
    print("\n" + "=" * 100)
    total = tp + tn + fp + fn
    print(f"ИТОГ: верно {tp+tn}/{total}  |  TP={tp} TN={tn}  ложные FP={fp}  пропуски FN={fn}")
    conn.close()


if __name__ == "__main__":
    main()
