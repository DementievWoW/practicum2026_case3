#!/usr/bin/env python3.10
"""
Универсальный сидер: интроспектит колонки каждой таблицы public и вставляет
N случайных строк по типам. FK/триггеры отключены (session_replication_role).
Не зависит от ручных seed-функций → обходит баги data_generator_db.py.

Запуск:  python3.10 scripts/seed_db_generic.py [N]
"""
import os
import sys
import random
import string

import psycopg2
from psycopg2.extras import execute_values
from faker import Faker

fake = Faker("ru_RU")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 500

CFG = dict(host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432"),
           dbname=os.getenv("DB_NAME", "demo_db"), user=os.getenv("DB_USER", "distr_user"),
           password=os.getenv("DB_PASSWORD", "pass"))


def value(name, dtype, maxlen):
    n = name.lower()
    if dtype in ("bigint", "integer"):
        return random.randint(1, 1000)
    if dtype == "smallint":
        return random.randint(0, 5)
    if dtype == "numeric":
        return round(random.uniform(0, 1_000_000), 2)
    if dtype.startswith("timestamp"):
        return fake.date_time_between(start_date="-5y", end_date="now")
    # строковые
    if "amount" in n:
        s = str(round(random.uniform(0, 1_000_000), 2))
    elif "passport" in n:
        s = f"{random.randint(1000, 9999)} {random.randint(100000, 999999)}"
    elif "snils" in n:
        s = f"{random.randint(100,999)}-{random.randint(100,999)}-{random.randint(100,999)} {random.randint(0,99):02d}"
    elif "inn" in n:
        s = str(random.randint(10**9, 10**12 - 1))
    elif "phone" in n:
        s = fake.phone_number()
    elif "email" in n:
        s = fake.email()
    elif "account" in n or "acc_num" in n or "check_account" in n:
        s = "".join(random.choices(string.digits, k=20))
    elif "name" in n:
        s = fake.company()
    else:
        s = "".join(random.choices(string.ascii_letters, k=8))
    return s[:maxlen] if maxlen else s


def main():
    conn = psycopg2.connect(**CFG)
    cur = conn.cursor()
    cur.execute("SET session_replication_role = 'replica';")  # выключаем FK/триггеры

    cur.execute("""SELECT table_name FROM information_schema.tables
                   WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name;""")
    tables = [r[0] for r in cur.fetchall()]

    ok, failed = 0, []
    for t in tables:
        cur.execute("""SELECT column_name, data_type, character_maximum_length
                       FROM information_schema.columns
                       WHERE table_schema='public' AND table_name=%s AND is_identity='NO'
                       ORDER BY ordinal_position;""", (t,))
        cols = cur.fetchall()
        if not cols:
            continue
        names = [c[0] for c in cols]
        rows = [tuple(value(c[0], c[1], c[2]) for c in cols) for _ in range(N)]
        collist = ", ".join(f'"{c}"' for c in names)
        sql = f'INSERT INTO public."{t}" ({collist}) VALUES %s ON CONFLICT DO NOTHING'
        try:
            execute_values(cur, sql, rows, page_size=500)
            conn.commit()
            ok += 1
        except Exception as e:
            conn.rollback()
            failed.append((t, str(e).splitlines()[0]))

    cur.execute("SET session_replication_role = 'origin';")
    conn.commit()

    print(f"✅ Заполнено таблиц: {ok}/{len(tables)}  (по ~{N} строк)")
    if failed:
        print(f"⚠️  Не удалось ({len(failed)}):")
        for t, err in failed:
            print(f"   {t}: {err}")

    cur.execute("""SELECT relname, n_live_tup FROM pg_stat_user_tables
                   WHERE schemaname='public' ORDER BY n_live_tup DESC LIMIT 10;""")
    print("\n📊 Top-10 по строкам:")
    for tbl, cnt in cur.fetchall():
        print(f"   {tbl:40s} {cnt:>7} строк")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
