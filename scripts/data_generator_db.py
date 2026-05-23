"""
Seed-скрипт для тестовой БД GreenData.
Заполняет все 60 таблиц минимум 1000 записей каждая,
с учётом FK-порядка и банковской специфики.

Запуск:
    python scripts/seed_db.py

Переменные окружения (или правка DB_CONFIG ниже):
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""
from __future__ import annotations

import os
import random
import string
from datetime import datetime, timedelta, date
from typing import Any, Iterable

import psycopg2
from psycopg2.extras import execute_values
from faker import Faker
from tqdm import tqdm

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "demo_db"),
    "user": os.getenv("DB_USER", "distr_user"),
    "password": os.getenv("DB_PASSWORD", "pass"),
}

MIN_ROWS = 1000          # Требование ментора
BATCH_SIZE = 1000        # Размер батча для execute_values
SEED = 42

fake = Faker("ru_RU")
Faker.seed(SEED)
random.seed(SEED)

# ---------------------------------------------------------------------------
# UTILS
# ---------------------------------------------------------------------------
def now() -> datetime:
    return datetime.now()

def random_date(start_year: int = 2018, end_year: int = 2026) -> date:
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def random_datetime(start_year: int = 2018, end_year: int = 2026) -> datetime:
    d = random_date(start_year, end_year)
    return datetime.combine(d, datetime.min.time()) + timedelta(
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )

def random_inn() -> str:
    """Генерация ИНН (10 цифр для ЮЛ)."""
    return "".join(random.choices(string.digits, k=10))

def random_phone() -> str:
    return f"+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}"

def random_smallint() -> int:
    return random.randint(0, 3)

def random_bigint_id(max_id: int) -> int:
    return random.randint(1, max(1, max_id))

def batch_insert(
    cur: psycopg2.extensions.cursor,
    table: str,
    columns: list[str],
    rows: Iterable[tuple],
    desc: str = "",
) -> int:
    """Быстрый batch-insert. Возвращает число вставленных строк."""
    cols = ", ".join(columns)
    sql = f"INSERT INTO public.{table} ({cols}) VALUES %s"
    data = list(rows)
    for i in tqdm(range(0, len(data), BATCH_SIZE), desc=desc or table, leave=False):
        chunk = data[i : i + BATCH_SIZE]
        execute_values(cur, sql, chunk, page_size=BATCH_SIZE)
    return len(data)


# ---------------------------------------------------------------------------
# ID-РЕЕСТРЫ (для связывания FK между слоями)
# ---------------------------------------------------------------------------
class IdRegistry:
    """Хранит сгенерированные ID, чтобы FK указывали на существующие записи."""

    def __init__(self) -> None:
        self.sys_state: list[int] = []
        self.sys_obj_type: list[int] = []
        self.sys_object: list[int] = []
        self.sys_employee: list[int] = []
        self.sys_company: list[int] = []
        self.business_segment: list[int] = []
        self.dict_product: list[int] = []
        self.offices_psb: list[int] = []
        self.scp_techcred: list[int] = []
        self.scp_dict_tech_ctredit: list[int] = []
        self.type_loan: list[int] = []
        self.scp_gov_program_dict: list[int] = []
        self.scp_prod_guarant_dict: list[int] = []
        self.scp_prod_comm_dict: list[int] = []
        self.scp_prod_guar_dict: list[int] = []
        self.acc_number: list[int] = []
        self.tbs_type: list[int] = []
        self.dict_div_presence: list[int] = []
        self.scp_dict_rsc_office: list[int] = []
        self.yaig_product_dict: list[int] = []
        self.cb_interest_rate: list[int] = []
        self.sys_algorithm: list[int] = []
        self.application_obj: list[int] = []
        self.credit_contract: list[int] = []
        self.fs_file: list[int] = []
        self.scp_application: list[int] = []
        self.ic_application: list[int] = []
        self.corp_tech_application: list[int] = []
        self.mler_application: list[int] = []
        self.scp_sec_expertise: list[int] = []
        self.participant_app: list[int] = []
        self.scp_collateral_app: list[int] = []
        self.scp_project_ans: list[int] = []
        self.scp_decision_quest: list[int] = []
        self.scp_sec_check_res: list[int] = []
        self.scp_part_sec_expertise: list[int] = []
        self.count_turnover: list[int] = []
        self.afhd_ac_trans_link: list[int] = []
        self.yaig_client_gen_agr: list[int] = []
        self.yaig_client_guarantee: list[int] = []
        self.scp_amd_product: list[int] = []
        self.product_pricing: list[int] = []
        self.prod_change_params: list[int] = []
        self.prod_commissions: list[int] = []
        self.prod_guarantees: list[int] = []
        self.sys_obj_resp: list[int] = []
        self.scp_dict_product_na: list[int] = []


# ---------------------------------------------------------------------------
# LAYER 0: СПРАВОЧНИКИ БЕЗ FK (или только на другие справочники)
# ---------------------------------------------------------------------------
def seed_sys_state(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    """Состояния объектов: предопределённые + сгенерированные."""
    base = [
        ("NEW", "Новый", "New"),
        ("IN_PROGRESS", "В работе", "In progress"),
        ("COMPLETED", "Завершён", "Completed"),
        ("REJECTED", "Отклонён", "Rejected"),
        ("CANCELLED", "Отменён", "Cancelled"),
        ("SUSPENDED", "Приостановлен", "Suspended"),
        ("APPROVED", "Согласован", "Approved"),
        ("SIGNED", "Подписан", "Signed"),
        ("ARCHIVED", "В архиве", "Archived"),
        ("DRAFT", "Черновик", "Draft"),
    ]
    rows = []
    for i in range(1, n + 1):
        if i <= len(base):
            ident, name_ru, name_en = base[i - 1]
        else:
            ident = f"STATE_{i:05d}"
            name_ru = f"Состояние {i}"
            name_en = f"State {i}"
        rows.append((
            i, name_ru, random_datetime(), 2, 1, 1, 1,
            ident, i, f"Описание состояния {i}",
            name_ru, name_en, 1, 1, 1, random_datetime(), 0,
        ))
    cols = [
        "id", "name", "create_date", "type_id", "status", "org_id", "user_id",
        "afr_ident", "afr_ord", "afr_note", "name__ru", "name__en",
        "created_emp_id", "last_modified_user_id", "last_modified_emp_id",
        "last_modified_date", "is_system",
    ]
    batch_insert(cur, "sys_state", cols, rows, desc="sys_state")
    reg.sys_state = list(range(1, n + 1))


def seed_sys_obj_type(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        ident = f"OBJ_TYPE_{i:05d}"
        rows.append((
            i, f"Тип объекта {i}", ident, f"table_{i}",
            None, f"pref_{i}_", 0, 0, 2, 1, 1,
            random_datetime(), 1, None, None, 0, 0, None, 0,
            1, 1, 1, random_datetime(), None, 0, None, 0,
            None, None, None, None, None, None, None, 0, 0, 0,
            None, None, None, None, 0, None, 0, None,
            f"Примечание {i}", f"Note {i}", f"Note {i}",
        ))
    cols = [
        "id", "name", "ident", "table_name", "parent_id", "field_name_prefix",
        "is_hierarchy", "is_system", "type_id", "org_id", "status",
        "create_date", "user_id", "name__en", "name__ru", "full_access_mask",
        "use_curmtx_rights", "java_handler", "not_copy",
        "created_emp_id", "last_modified_user_id", "last_modified_emp_id",
        "last_modified_date", "obj_type_attr_id", "is_time_depended",
        "js_handler", "is_readonly_by_default", "alg_saving_id", "alg_saved_id",
        "id_seq_name", "ext_types_multiselect", "use_cache",
        "hist_attr_force_create", "link_access_attr_id", "access_type_id",
        "ext_types_widget_name", "ext_types_hide_btn", "rf_connection",
        "attr_with_name", "alg_deleting_id", "display_obj_inst",
        "is_enabled_change_audit", "allow_ignore_lifecycle",
        "sys_content_type_id", "init_cache", "sys_obj_type_is_mdata",
        "note", "note__ru", "note__en",
    ]
    batch_insert(cur, "sys_obj_type", cols, rows, desc="sys_obj_type")
    reg.sys_obj_type = list(range(1, n + 1))


def seed_business_segment(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    base = ["Микро", "Малый", "Средний", "Крупный", "VIP", "Корпоративный",
            "Стартап", "Гос.компания", "ИП", "ФЛ-предприниматель"]
    rows = []
    for i in range(1, n + 1):
        name = base[i - 1] if i <= len(base) else f"Сегмент {i}"
        rows.append((
            i, name, name, name, random_datetime(), 2, 1, 1, 1,
            random_datetime(), 1, 1, 1, random_datetime(), 0,
            f"BS_{i:05d}", i,
        ))
    cols = [
        "id", "name__en", "name__ru", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system", "ident", "type_int_code",
    ]
    batch_insert(cur, "business_segment", cols, rows, desc="business_segment")
    reg.business_segment = list(range(1, n + 1))


def seed_scp_techcred(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Технология {i}", f"Tech {i}", random_datetime(),
            2, 1, 1, 1, random_datetime(), 1, 1, 1, random_datetime(),
            0, i, f"TECH_{i:05d}", i, f"Tech {i}", 1,
        ))
    cols = [
        "id", "name__ru", "name", "create_date", "type_id", "status",
        "org_id", "user_id", "last_modified_date", "last_modified_user_id",
        "last_modified_emp_id", "created_emp_id", "last_modified_emp_id",
        "is_system", "ord", "ident", "type_int_code", "name__en", "is_available",
    ]
    batch_insert(cur, "scp_techcred", cols, rows, desc="scp_techcred")
    reg.scp_techcred = list(range(1, n + 1))


def seed_scp_dict_tech_ctredit(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Технология кредитования {i}", f"Тех Kred {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, i, f"TECHCR_{i:05d}", i, f"TechCred {i}", 1,
        ))
    cols = [
        "id", "name__ru", "name", "create_date", "type_id", "status",
        "org_id", "user_id", "last_modified_date", "last_modified_user_id",
        "last_modified_emp_id", "created_emp_id", "last_modified_emp_id",
        "is_system", "ord", "ident", "type_int_code", "name__en", "is_available",
    ]
    batch_insert(cur, "scp_dict_tech_ctredit", cols, rows, desc="scp_dict_tech_ctredit")
    reg.scp_dict_tech_ctredit = list(range(1, n + 1))


def seed_type_loan(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    base = ["Кредитная линия", "Овердрафт", "Разовый кредит", "Банковская гарантия",
            "Факторинг", "Лизинг", "Аккредитив", "Ипотека", "Эскроу", "Синдицированный"]
    rows = []
    for i in range(1, n + 1):
        name = base[i - 1] if i <= len(base) else f"Вид кредита {i}"
        rows.append((
            i, name, name, random_datetime(), 2, 1, 1, 1,
            random_datetime(), 1, 1, 1, random_datetime(), 0,
            None, i, f"LOAN_{i:05d}", 1, i, name,
        ))
    cols = [
        "id", "name__ru", "name", "create_date", "type_id", "status",
        "org_id", "user_id", "last_modified_date", "last_modified_user_id",
        "last_modified_emp_id", "created_emp_id", "last_modified_emp_id",
        "is_system", "prod_type_upp_lev_id", "ord", "ident",
        "rel_submis_form", "seq_prod_number", "name__en",
    ]
    batch_insert(cur, "type_loan", cols, rows, desc="type_loan")
    reg.type_loan = list(range(1, n + 1))


def seed_dict_div_presence(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    regions = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
               "Казань", "Нижний Новгород", "Самара", "Ростов-на-Дону",
               "Уфа", "Красноярск", "Воронеж", "Пермь", "Волгоград",
               "Краснодар", "Саратов", "Тюмень", "Тольятти", "Ижевск",
               "Барнаул", "Иркутск"]
    rows = []
    for i in range(1, n + 1):
        region = regions[i - 1] if i <= len(regions) else f"Регион {i}"
        code = f"{i:02d}"
        rows.append((
            i, region, region, random_datetime(), 2, 1, 1, 1,
            random_datetime(), 1, 1, 1, random_datetime(), 0, i,
            region, code, 1,
            random.choice([0, 1]), random.choice([0, 1]), random.choice([0, 1]),
            region,
        ))
    cols = [
        "id", "name__ru", "name", "create_date", "type_id", "status",
        "org_id", "user_id", "last_modified_date", "last_modified_user_id",
        "last_modified_emp_id", "created_emp_id", "last_modified_emp_id",
        "is_system", "ord", "nameregion", "coderegion", "div_presence",
        "stop_region", "stop_region_ko", "stop_region_fact", "name__en",
    ]
    batch_insert(cur, "dict_div_presence", cols, rows, desc="dict_div_presence")
    reg.dict_div_presence = list(range(1, n + 1))


def seed_cb_interest_rate(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    base_rate = 7.5
    for i in range(1, n + 1):
        start = random_datetime(2015, 2025)
        end = start + timedelta(days=random.randint(30, 365))
        rate = round(base_rate + random.uniform(-3, 10), 2)
        rows.append((
            i, f"Ставка ЦБ {i}", f"CB Rate {i}", f"CBR_{i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, start, end, rate,
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system", "date_start_cb", "date_end_cb",
        "grade_number_cb",
    ]
    batch_insert(cur, "cb_interest_rate", cols, rows, desc="cb_interest_rate")
    reg.cb_interest_rate = list(range(1, n + 1))


def seed_tbs_type(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Тип ОСВ {i}", f"TBS {i}", random_datetime(), 2, 1, 1, 1,
            random_datetime(), 1, 1, 1, random_datetime(), 0, i,
            f"TBS_{i:05d}", None, f"TBS {i}",
        ))
    cols = [
        "id", "name__ru", "name", "create_date", "type_id", "status",
        "org_id", "user_id", "last_modified_date", "last_modified_user_id",
        "last_modified_emp_id", "created_emp_id", "last_modified_emp_id",
        "is_system", "ord", "identif", "acc_subconto_type_id", "name__en",
    ]
    batch_insert(cur, "tbs_type", cols, rows, desc="tbs_type")
    reg.tbs_type = list(range(1, n + 1))


def seed_acc_number(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        acc_num = f"{random.randint(40000, 49999):05d}.{random.randint(100, 999):03d}"
        rows.append((
            i, f"Счёт {acc_num}", f"Acc {acc_num}", random_datetime(),
            2, 1, 1, 1, random_datetime(), 1, 1, 1, random_datetime(),
            0, i, None, f"Счёт/Субсчёт {acc_num}", f"Account {acc_num}",
        ))
    cols = [
        "id", "name__ru", "name", "create_date", "type_id", "status",
        "org_id", "user_id", "last_modified_date", "last_modified_user_id",
        "last_modified_emp_id", "created_emp_id", "last_modified_emp_id",
        "is_system", "ord", "parent_acc", "account_name", "name__en",
    ]
    batch_insert(cur, "acc_number", cols, rows, desc="acc_number")
    reg.acc_number = list(range(1, n + 1))


def seed_scp_gov_program_dict(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Госпрограмма {i}", f"GovProgram {i}", f"GP_{i:05d}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, i, f"GOV_{i:05d}",
            round(random.uniform(1, 5), 2), round(random.uniform(5, 15), 2),
            round(random.uniform(1, 7), 2), None, None,
            random_datetime(2025, 2030), round(random.uniform(2, 8), 2),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system", "ord", "ident",
        "scp_max_margin_val", "scp_max_pref_rate_val", "scp_subsidy_rate_val",
        "type_gov_prog_id", "upp_gov_prog_dict_id", "date_end_cb",
        "scp_fund_rate_val",
    ]
    batch_insert(cur, "scp_gov_program_dict", cols, rows, desc="scp_gov_program_dict")
    reg.scp_gov_program_dict = list(range(1, n + 1))


def seed_scp_prod_guarant_dict(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Гарантия {i}", f"Guarantee {i}", f"GRT_{i:05d}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, i, f"GUAR_{i:05d}", i,
            round(random.uniform(0.5, 3), 2), random.randint(10000, 500000),
            random.randint(10000, 100000), random.randint(500000, 5000000),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system", "ord", "ident",
        "guarantee_type_id", "bank_val_proc", "bank_val_sum",
        "sum_from", "sum_to",
    ]
    batch_insert(cur, "scp_prod_guarant_dict", cols, rows, desc="scp_prod_guarant_dict")
    reg.scp_prod_guarant_dict = list(range(1, n + 1))


def seed_scp_prod_comm_dict(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Комиссия {i}", f"Commission {i}", f"COM_{i:05d}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, i, f"COMM_{i:05d}",
            f"Ежемесячно", f"{round(random.uniform(0.1, 3), 2)}%",
            f"Описание комиссии {i}", f"Тариф {i}", 0,
            round(random.uniform(0.1, 5), 2), random.choice([0, 1]),
            i, None, None, 0, 0, 0, 0, None, random.randint(100, 10000),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system", "ord", "ident",
        "scp_payment_shedule_str", "scp_comiss_size_str", "value_comment",
        "fare_description", "is_ho_application", "com_val_proc",
        "is_for_state_program", "gov_prog_value", "payment_schedule_id",
        "new_com_val_proc", "scp_gov_program_id", "is_corp_tech_bool",
        "is_product_log_bool", "is_actual_comission", "is_apk_tech_bool",
        "change_comiss_dict_id", "bank_val_sum",
    ]
    batch_insert(cur, "scp_prod_comm_dict", cols, rows, desc="scp_prod_comm_dict")
    reg.scp_prod_comm_dict = list(range(1, n + 1))


def seed_scp_prod_guar_dict(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Гарантия продукта {i}", f"ProdGuar {i}", f"PG_{i:05d}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, i, f"PRGU_{i:05d}",
            f"{round(random.uniform(0.5, 2), 2)}%", "Ежеквартально",
            f"Описание гарантии {i}", round(random.uniform(0.5, 3), 2),
            random_bigint_id(n), random.choice([0, 1]), None, None, None,
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system", "ord", "ident",
        "scp_comiss_size_str", "scp_payment_shedule_str", "value_comment",
        "com_val_proc", "prod_guarant_dict_id", "gov_prog_value",
        "payment_schedule_id", "new_com_val_proc", "scp_gov_program_id",
    ]
    batch_insert(cur, "scp_prod_guar_dict", cols, rows, desc="scp_prod_guar_dict")
    reg.scp_prod_guar_dict = list(range(1, n + 1))


def seed_dict_product(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    base = [
        "Кредитная линия МСБ", "Овердрафт Бизнес", "Разовый кредит",
        "Банковская гарантия", "Факторинг", "Ипотека коммерческая",
        "Эскроу-счёт", "Лизинг оборудования", "Аккредитив",
        "Инвестиционный кредит",
    ]
    rows = []
    for i in range(1, n + 1):
        name = base[i - 1] if i <= len(base) else f"Продукт {i}"
        rows.append((
            i, name, name, name, random_datetime(), 2, 1, 1, 1,
            random_datetime(), 1, 1, 1, random_datetime(), 0,
            None, None, None, random_bigint_id(n), None, None, None,
            None, None, None, None, None, 1, 1, 1, 1, None, 1, None,
            round(random.uniform(1, 25), 2), None, random.randint(1, 365),
            1, None, random.randint(3, 36), random.randint(1, 12),
            random.randint(1, 30), None, random.randint(6, 60),
            random.randint(1, 60), random.randint(100000, 10000000),
            random.randint(1000000, 100000000), random.randint(100000, 5000000),
            None, round(random.uniform(2, 15), 2), random.randint(30, 365),
            None, None, None, 1, random.randint(1, 24), random.randint(1, 12),
            None, None, None, None, None, None, None, f"PROD_{i:05d}",
            random.randint(30, 365), 0, None, None, None, None, None,
            None, None, None, round(random.uniform(5, 20), 2), None,
            random.randint(6, 60), f"{random.randint(1,12)}/{random.randint(1,12)}",
            f"{random.randint(1,12)}/{random.randint(1,12)}", 1,
            random.randint(12, 120), None, None, None, None, None, None,
            None, None, 1, 0, f"Контрактная группа {i}", 1, 0, 0, 0,
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "collateral_id", "guarantee_id", "departure_id",
        "attr_business_segment", "interest_penalties_id", "lending_type_id",
        "volume_revenue_id", "number_transactions_id", "amount_tender_loan_id",
        "payment_method_id", "overdraft_limit_id", "max_amount_id",
        "payment_interest_id", "possibility_delay", "payment_account",
        "early_rep_pos", "necessity_insurance", "payment_commission_id",
        "installment_payment", "rate_increase_1", "id_855918", "guarantee_1",
        "min_sum", "type_of_guarantee_id", "product_relevance",
        "comissions_id", "ident", "valid_decision", "indefinite_period",
        "form_issue_id", "part_big_buyer", "num_months_cashbox",
        "num_months_income", "count_income_month", "limit_over",
        "summ_tranche", "summ_limit", "term_limit_credit", "max_sum_credit",
        "min_sum_credit", "forfeight_id", "transfert_rate", "debt_on_tranche",
        "type_limit_over_id", "tech_decision_id", "credit_interest_rate",
        "dynam_type_id", "form_limit", "loan_terms", "issue_limit_second",
        "issue_limit_first", "is_early_repay", "max_loan_term",
        "period_grace", "card_validity", "lp_product_code", "dbo_product_code",
        "cp_product_code", "limit_term", "finstar_product_code",
        "factoring_product_code", "is_simplified_fa", "is_package",
        "name_contr_group", "is_insurance_available", "is_amd_fill_mandatory",
        "is_new_prod_for_ns", "is_fin_activ_newsub",
    ]
    batch_insert(cur, "dict_product", cols, rows, desc="dict_product")
    reg.dict_product = list(range(1, n + 1))


def seed_offices_psb(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    cities = ["Москва", "Санкт-Петербург", "Екатеринбург", "Новосибирск",
              "Казань", "Нижний Новгород", "Самара", "Ростов-на-Дону"]
    rows = []
    for i in range(1, n + 1):
        city = cities[i % len(cities)]
        rows.append((
            i, f"Офис {i}", f"Office {i}", f"OF_{i:05d}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, None, f"Офис {i}", f"Off {i}", f"O{i}",
            None, None, None, f"OFF_{i:05d}", f"OFC{i:05d}",
            f"{city}, ул. Ленина, {i}", f"{i:05d}",
            random_datetime(2010, 2023), None, "Доп. офис", "Универсальный",
            1, None, None, i, random.choice([0, 1]),
            random.choice([0, 1]), 1, 0, None, None, None,
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system", "parent_org_id",
        "short_name__ru", "short_name__en", "short_name", "view_id",
        "main_org", "org_company", "ident", "office_id", "office_name",
        "office_address", "office_code", "office_date_from", "office_date_to",
        "office_type", "office_status", "office_sign_active", "psb_dep_org",
        "rout_office_id", "lvl_org", "feat_org", "is_region", "work_org",
        "etl_marker_org", "id_parent_org", "id_depart_org",
        "id_parent_corr_org",
    ]
    batch_insert(cur, "offices_psb", cols, rows, desc="offices_psb")
    reg.offices_psb = list(range(1, n + 1))


def seed_scp_dict_rsc_office(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Офис РЦБ {i}", f"RSC Office {i}", f"RSC_{i:05d}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, i, f"RSC_OFF_{i:05d}",
            random_bigint_id(n),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system", "ord", "ident", "rsc_office_id",
    ]
    batch_insert(cur, "scp_dict_rsc_office", cols, rows, desc="scp_dict_rsc_office")
    reg.scp_dict_rsc_office = list(range(1, n + 1))


def seed_yaig_product_dict(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"УАиГ продукт {i}", f"YAIG Prod {i}", f"YP_{i:05d}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, f"YAIG_{i:05d}",
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system", "ident",
    ]
    batch_insert(cur, "yaig_product_dict", cols, rows, desc="yaig_product_dict")
    reg.yaig_product_dict = list(range(1, n + 1))


def seed_sys_algorithm(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Alg v{i}", f"Алг в{i}", f"Алгоритм {i}",
            random_datetime(), 2, 1, 1, 1, f"ALG_{i:05d}",
            f"x + {i}", 1, 2, 0, f"compiled_{i}",
            1, 1, 1, random_datetime(), 0, i, f"Algorithm {i}", 0,
        ))
    cols = [
        "id", "name__en", "name__ru", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "amy_ident", "amy_frml_text",
        "amy_alg_type_id", "amy_base_type_id", "amy_sys_alg_not_replace_null",
        "amy_compiled_code", "created_emp_id", "last_modified_user_id",
        "last_modified_emp_id", "last_modified_date", "is_system",
        "amy_ver_num", "amy_alg_name", "amy_use_null_if_src_empty",
    ]
    batch_insert(cur, "sys_algorithm", cols, rows, desc="sys_algorithm")
    reg.sys_algorithm = list(range(1, n + 1))


# ---------------------------------------------------------------------------
# LAYER 1: БАЗОВЫЕ СУЩНОСТИ (ссылаются на справочники)
# ---------------------------------------------------------------------------
def seed_sys_company(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    """Клиенты/контрагенты. Содержит PII (inn, phone, email) — для аудита."""
    seen_inn = set()
    rows = []
    for i in range(1, n + 1):
        company_name = fake.company()
        inn = random_inn()
        while inn in seen_inn:
            inn = random_inn()
        seen_inn.add(inn)
        rows.append((
            i, company_name, company_name[:50], inn, 2, 1, 1,
            random_datetime(), 1, f"{company_name} (en)", f"{company_name} (ru)",
            fake.email(), fake.url(), 1, 1, 1, random_datetime(), 0,
            "Россия", random_phone(), random_bigint_id(n),
            random_bigint_id(n), random_datetime(), None,
            random_datetime(), f"Регистратор {i}", f"Налоговая {i}",
            f"CRM_{i:07d}", fake.city(), fake.street_address(),
            fake.street_address(), fake.city(), f"ABS_{i}",
            f"ИФНС {i}", f"ИФНС-учёт {i}", random_bigint_id(n),
            random.choice([0, 1]), random_datetime(), random.choice([0, 1]),
            random_bigint_id(n), random.choice([0, 1]),
            random_bigint_id(n), random.choice([0, 1]),
            random_bigint_id(n), random_bigint_id(n),
            random_datetime(), random.choice([0, 1]), random_datetime(),
            random_bigint_id(n), random_bigint_id(n),
            random.choice([0, 1]), random_bigint_id(n),
            fake.text(max_nb_chars=100), fake.text(max_nb_chars=100),
            random.choice([0, 1]), random_bigint_id(n),
            random.choice([0, 1, 2]), random.choice([0, 1]),
        ))
    cols = [
        "id", "name", "short_name", "inn", "type_id", "org_id", "status",
        "create_date", "user_id", "name__en", "name__ru", "attr_email",
        "attr_web_site", "created_emp_id", "last_modified_user_id",
        "last_modified_emp_id", "last_modified_date", "is_system",
        "attr_reg_country", "contact_phone", "main_okved", "business_segment",
        "comp_reg_date", "group_company_link", "company_record_date",
        "company_registrator", "company_tax_authority", "crmd_client_id",
        "act_addr_city", "act_addr_street", "reg_addr_street", "reg_addr_city",
        "attr_attr_abs", "tax_authority_reg", "tax_authority_account",
        "customer_type_id", "sign_of_sme", "date_of_registration",
        "newly_founded", "offices_psb_id", "sign_of_bankruptcy",
        "stage_of_bankruptcy", "granting_consent", "date_of_consent",
        "fo_okved", "busines_segment_id", "d_storage_balance_txt",
        "d_storage_finrep_txt", "is_rko", "afina_segment_id",
        "neg_comment", "neg_status", "attr_launch_neg_etl",
    ]
    batch_insert(cur, "sys_company", cols, rows, desc="sys_company")
    reg.sys_company = list(range(1, n + 1))


def seed_sys_employee(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    """Сотрудники. Содержит PII: email, phone, birthday."""
    seen_email = set()
    rows = []
    for i in range(1, n + 1):
        first = fake.first_name()
        last = fake.last_name()
        email = fake.email()
        while email in seen_email:
            email = fake.email()
        seen_email.add(email)
        rows.append((
            i, f"{last} {first}", 2, 1, 1, random_datetime(), 1, 1,
            f"{last} {first} (en)", f"{last} {first} (ru)",
            first, fake.first_name(), last, random_bigint_id(n),
            email, random_datetime(1960, 2000), random_phone(),
            f"skype_{i}", 1, 1, 1, random_datetime(), 0,
            3, None, 0, None, 1, 1, 0, random_bigint_id(n),
            random.choice([1, 2]), 1, last, last, first, first,
            fake.first_name(), fake.first_name(), random_bigint_id(n),
            f"AD_{i}", f"EMP_{i:07d}", f"+7(495)000{i:04d}",
            random_bigint_id(n),
        ))
    cols = [
        "id", "name", "type_id", "org_id", "status", "create_date",
        "user_id", "emp_org_id", "name__en", "name__ru", "first_name",
        "second_name", "sur_name", "job_pos_id", "email", "birthday",
        "phone", "skype", "created_emp_id", "last_modified_user_id",
        "last_modified_emp_id", "last_modified_date", "is_system",
        "time_zone", "sys_image", "is_locked", "workday_schedule_id",
        "email_confirmed", "phone_confirmed", "ban_send_notifications",
        "city_id", "sex_id", "locale_id", "sur_name__ru", "sur_name__en",
        "first_name__ru", "first_name__en", "second_name__ru",
        "second_name__en", "ps_office", "adress_ad", "pers_emp_number",
        "inner_emp_phone", "pers_opt_dmm_link",
    ]
    batch_insert(cur, "sys_employee", cols, rows, desc="sys_employee")
    reg.sys_employee = list(range(1, n + 1))


def seed_sys_object(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    """Универсальная таблица объектов (на неё ссылаются многие через obj_owner_id)."""
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Объект {i}", random_bigint_id(n), 1, 1,
            random_datetime(), 1, f"Object {i}", f"Объект {i}",
            1, 1, 1, random_datetime(), 0,
        ))
    cols = [
        "id", "name", "type_id", "org_id", "status", "create_date",
        "user_id", "name__en", "name__ru", "created_emp_id",
        "last_modified_user_id", "last_modified_emp_id",
        "last_modified_date", "is_system",
    ]
    batch_insert(cur, "sys_object", cols, rows, desc="sys_object")
    reg.sys_object = list(range(1, n + 1))


def seed_fs_file(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        fname = f"doc_{i:07d}.pdf"
        rows.append((
            i, fname, 2, 1, 1, random_datetime(), 1, 1, 1,
            f"inner_{fname}", random.randint(1024, 10_000_000), 1,
            f"Документ {i}", random_datetime(2025, 2028),
            fname, fname, 1, 1, 1, random_datetime(), 0,
            random_bigint_id(n), 1, random_datetime(), f"cls_{i}",
            random_datetime(), 0, f"{i}.pdf",
            random_datetime(), random_datetime(), f"uuid-{i:08d}",
        ))
    cols = [
        "id", "name", "type_id", "org_id", "status", "create_date",
        "user_id", "ff_type_id", "ff_storage_id", "ff_inner_name",
        "ff_body_size", "ff_kind_id", "ff_note", "ff_actual_end_date",
        "name__en", "name__ru", "created_emp_id", "last_modified_user_id",
        "last_modified_emp_id", "last_modified_date", "is_system",
        "ff_parent_object", "ff_is_stored", "ff_id_881754", "ff_id_881762",
        "ff_id_881752", "ff_fs_is_preview_file", "ff_fs_file_name",
        "ff_fv_date_from", "ff_fv_date_to", "ff_body_uuid",
    ]
    batch_insert(cur, "fs_file", cols, rows, desc="fs_file")
    reg.fs_file = list(range(1, n + 1))


# ---------------------------------------------------------------------------
# LAYER 2: БИЗНЕС-ОБЪЕКТЫ
# ---------------------------------------------------------------------------
def seed_application_obj(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Заявка {i}", f"App {i}", f"Application {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, f"DOC-{i:07d}", random_datetime(),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n), None,
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), f"Продукт {i}", random.choice([0, 1]),
            f"Технология {i}", random.choice([0, 1]), None,
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system", "afl_doc_num", "afl_doc_data",
        "afp_state_id", "initiator_id", "emp_id", "processing_steps_id",
        "temp_cont_turn", "cr_id", "scp_tech_ctredit",
        "scp_business_segment", "client_type_id", "gsl_data_cont_id",
        "industry_code_id", "scp_product_str", "is_state_program",
        "cred_technology_str", "is_fin_activ_newsub", "prelim_gsl_calc_id",
    ]
    batch_insert(cur, "application_obj", cols, rows, desc="application_obj")
    reg.application_obj = list(range(1, n + 1))


def seed_credit_contract(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    """Кредитные договоры. Содержат PII: check_account, bank_ident_number."""
    seen_ccn = set()
    rows = []
    for i in range(1, n + 1):
        ccn = f"CC-{random.randint(2018,2025)}-{i:06d}"
        while ccn in seen_ccn:
            ccn = f"CC-{random.randint(2018,2025)}-{random.randint(1,999999):06d}"
        seen_ccn.add(ccn)
        start = random_datetime(2018, 2024)
        end = start + timedelta(days=random.randint(180, 365 * 5))
        rows.append((
            i, f"КД {ccn}", f"CC {ccn}", f"Credit Contract {ccn}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, ccn, start, 1, ccn,
            random.randint(6, 60), round(random.uniform(100_000, 50_000_000), 2),
            f"Назначение {i}", f"Категория {i}",
            random.choice(["Хорошее", "Среднее", "Плохое"]),
            round(random.uniform(1, 30), 2), random_bigint_id(n),
            random_bigint_id(n), round(random.uniform(5, 25), 2),
            random_bigint_id(n), start, end,
            f"{random.randint(40700, 40799):05d}810{random.randint(100000000,999999999):09d}",
            str(random.randint(0, 90)), f"Class_{i}", f"Group_{i}",
            round(random.uniform(0, 10_000_000), 2), random_bigint_id(n),
            random.choice(["КЛ", "ОВ", "БГ", "Факторинг"]),
            f"Продукт {i}", random_bigint_id(n), random.choice([0, 1]),
            random_bigint_id(n), random_bigint_id(n), random_bigint_id(n),
            random.choice([0, 1]), fake.last_name(), fake.first_name(),
            fake.first_name(), f"TN{i:07d}", random_bigint_id(n),
            random_bigint_id(n), random.choice([0, 1]), f"OFFER-{i:07d}",
            f"KK-{i:06d}", str(random_datetime()), f"Субсидия {i}",
            f"{random.randint(100000000,999999999):09d}", None, None, None,
            None, None, random_bigint_id(n), random.choice([0, 1]),
            random.randint(0, 365), None, f"ФА {fake.last_name()}",
            f"UID-{i:010d}", round(random.uniform(1_000_000, 100_000_000), 2),
            random_datetime(2025, 2028), round(random.uniform(0.1, 5), 2),
            random.choice([0, 1]), f"TN{i:07d}",
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "afl_doc_num", "afl_doc_data", "afp_state_id",
        "credit_contract_number", "loan_term", "credit_amount",
        "special_purpose", "quality_categor", "financial_position",
        "reserve_size", "link_customer_id", "aplication_id",
        "cred_interest_rate", "sel_curr", "credit_start_date",
        "credit_end_date", "check_account", "days_delay_number",
        "loan_classified", "contract_group", "date_loan_debt",
        "prof_judg_id", "contract_type", "credit_product",
        "applic_ko_kbkp_id", "is_closed", "pledge_contract_id",
        "wf_document_id", "cr_status_id", "is_guarantee", "lname", "fname",
        "mname", "tabnum", "sys_employee_id", "subsidy_prog_id",
        "individ_guarantee", "offer_ident", "number_kk", "protocol_date",
        "subsidy_prog_str", "bank_ident_number",
        "tech_link_etl_susp_id", "suspension_na_id", "tech_link_etl_state_id",
        "appl_documentum_num", "supplement_tech", "contracttype",
        "tech_selected_rz_id", "tech_selected_comm", "tech_selected_meas_id",
        "yaig_base_code", "hand_suspension", "duration_over_on_date",
        "close_contract", "fa_specialist", "uid_credit",
        "max_loan_amount_ever", "exite_date", "penalty_rate",
        "is_tranche_exist", "pers_emp_number",
    ]
    batch_insert(cur, "credit_contract", cols, rows, desc="credit_contract")
    reg.credit_contract = list(range(1, n + 1))


def seed_count_turnover(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        start = random_datetime(2020, 2025)
        end = start + timedelta(days=random.randint(30, 365))
        rows.append((
            i, random_bigint_id(n), random.choice([0, 1]),
            end, random.randint(1, 12), f"ОСВ {i}", f"OSV {i}", f"TO {i}",
            start, random_bigint_id(n), f"src_{i}",
            round(random.uniform(0, 10_000_000), 2),
            round(random.uniform(0, 10_000_000), 2),
            random.choice([0, 1]), f"{start.year}-{start.month:02d}",
            random_bigint_id(n),
            round(random.uniform(0, 5_000_000), 2),
            round(random.uniform(0, 5_000_000), 2),
            round(random.uniform(0, 5_000_000), 2),
            round(random.uniform(0, 5_000_000), 2),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), 0, random_bigint_id(n),
            random.choice([0, 1]), round(random.uniform(0, 20), 2),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
            round(random.uniform(0, 5_000_000), 2),
            round(random.uniform(0, 5_000_000), 2),
            random_bigint_id(n), random_bigint_id(n),
        ))
    cols = [
        "id", "link_cnt_owner", "double_turn_balance", "finish_period",
        "count_months", "name", "name__ru", "name__en", "st_period",
        "account_num_id", "account_source", "turnover_debit",
        "turnover_credit", "is_check", "period_st_end", "parent_link_count",
        "output_balance_debit", "output_balance_credit",
        "input_balance_debit", "input_balace_credit", "link_cred_doc_tur",
        "link_load_val_id", "link_partic_gr", "is_del", "correct_type",
        "tech_manual_vat", "vat", "bb_debet_id", "bb_cred_id",
        "bb_debet_reclass_id", "bb_cred_reclass_id", "out_bal_recl_debt",
        "out_bal_recl_cred", "bb_debet_input_id", "bb_cred_input_id",
    ]
    batch_insert(cur, "count_turnover", cols, rows, desc="count_turnover")
    reg.count_turnover = list(range(1, n + 1))


def seed_afhd_ac_trans_link(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), round(random.uniform(0.5, 2), 2),
            random_datetime(), round(random.uniform(1000, 1_000_000), 2),
            round(random.uniform(1000, 1_000_000), 2),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), round(random.uniform(0, 20), 2),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), fake.company(), fake.company(),
            random.choice([0, 1]), random_bigint_id(n),
            round(random.uniform(0, 20), 2), random_bigint_id(n),
            random_datetime(), round(random.uniform(0, 10), 2),
            random_bigint_id(n),
        ))
    cols = [
        "id", "obj_owner_id", "transaction_id", "source_row_id",
        "reclass_row_id", "dummy_row_id", "debit_credit_id", "comp_sign_id",
        "form_inst_id", "form_section_id", "consolidation_obj_id",
        "statem_trans_id", "multiply_val", "account_date", "after_amount",
        "before_amount", "is_excepted", "is_intragroup", "is_psb_trans",
        "copy_source_ac_tr_l_id", "link_turnover", "tbs_item_id",
        "multiplicator_sign_id", "link_calc_turn_log_id",
        "okved_activity_id", "vat", "balance_type_id", "account_num_id",
        "link_cnt", "cnt_count", "contragent_name", "is_clean_apply",
        "cnt_turnover_id", "vat_calc", "link_turnover_reserv",
        "report_date", "discount", "cr_id",
    ]
    batch_insert(cur, "afhd_ac_trans_link", cols, rows, desc="afhd_ac_trans_link")
    reg.afhd_ac_trans_link = list(range(1, n + 1))


def seed_participant_app(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Участник {i}", f"Участник {i}", random_datetime(),
            2, 1, 1, 1, random_datetime(), 1, 1, 1, random_datetime(), 0,
            random_bigint_id(n), random_bigint_id(n),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(n), random.choice([0, 1]),
            random_datetime(), random_datetime(), random.choice([0, 1]),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(n), random.choice([0, 1]),
            random.choice([0, 1]), f"Роль {i}",
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), None, f"SIAM_{i:07d}",
            random_datetime(), random.choice([0, 1]),
            random.choice([0, 1]), random_bigint_id(n),
            random_bigint_id(n), random.choice([0, 1]),
            random.choice([0, 1]), random_datetime(),
            random.choice([0, 1]), None, random_bigint_id(n),
            f"Участник {i}", random_bigint_id(n),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice(["Активен", "Неактивен", "В работе"]),
        ))
    cols = [
        "id", "name__ru", "name", "create_date", "type_id", "status",
        "org_id", "user_id", "last_modified_date", "last_modified_user_id",
        "last_modified_emp_id", "created_emp_id", "last_modified_emp_id",
        "is_system", "app_obj_id", "borrower_id", "is_current",
        "is_check_need", "part_type_id", "is_permanent_role",
        "sec_date_check", "sec_appeal_date", "is_sec_appeal",
        "is_antifrod_success", "is_perm_role_for_head", "emp_appeal_id",
        "is_create_check", "is_add_manual", "check_role_part_str",
        "is_borrower", "is_related_entity", "is_affiliate", "is_pledger",
        "is_guarantor", "return_code_txt", "id_siam_str", "consentbkidate",
        "is_bch_form_error", "is_seller", "scp_link_particip_id",
        "particip_sec_id", "is_guar_prov_balhold", "is_state_affilation",
        "sec_check_auto_date", "bch_refuse", "bch_record_link",
        "app_obj_person_conn_id", "name__en", "obj_owner_id",
        "is_director", "is_actual_owner", "is_founder", "is_legal_person",
        "bki_status",
    ]
    batch_insert(cur, "participant_app", cols, rows, desc="participant_app")
    reg.participant_app = list(range(1, n + 1))


# ---------------------------------------------------------------------------
# LAYER 3: ЗАЯВКИ СКП / ИУ / КТ / МЛЕР
# ---------------------------------------------------------------------------
def _application_base(i: int):
    """Общие поля для всех *application таблиц."""
    return (
        i, f"Заявка {i}", f"App {i}", f"Application {i}",
        random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
        random_datetime(), 0, f"DOC-{i:07d}", random_datetime(),
        random_bigint_id(1000), random_bigint_id(1000),
        random_bigint_id(1000), random_bigint_id(1000), None,
        random_bigint_id(1000), random_bigint_id(1000),
        random_bigint_id(1000), random_bigint_id(1000),
        random_bigint_id(1000), round(random.uniform(100000, 50000000), 2),
        random_bigint_id(1000), random_bigint_id(1000),
        random_bigint_id(1000),
    )


def seed_scp_application(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        base = _application_base(i)
        rows.append(base + (
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), f"Исполнитель {i}",
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            f"ГСЛ {i}", fake.text(max_nb_chars=100),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            f"http://suz/{i}", random.choice([0, 1]),
            random_bigint_id(1000), fake.text(max_nb_chars=200),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            random.randint(6, 60), random.choice([0, 1]),
            random_bigint_id(1000), random.choice([0, 1]),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            f"Продукт {i}", random.choice([0, 1]),
            f"Технология {i}", random.choice([0, 1]),
            random.choice([0, 1]), random.choice([0, 1]), None,
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "afl_doc_num", "afl_doc_data", "afp_state_id", "initiator_id",
        "req_type_id", "lim_sum", "loan_terms", "lim_currency_id",
        "gsl_limit", "credit_logic_id", "lending_tech_id", "emp_id",
        "processing_steps_id", "scp_curr_emp", "temp_cont_turn",
        "risk_zone_id", "calc_risk_date", "is_active_exp_sec", "cr_id",
        "scp_appl_type_id", "deleg_region_id", "scp_hcm_decision_id",
        "is_active_get_gsl_part", "scp_tech_ctredit",
        "scp_business_segment", "is_start_bp_fa", "is_tech_ham_task_comp",
        "is_collat_exp_launched", "is_simplified_fa",
        "is_start_bp_request_fa", "auto_check_status", "client_type_id",
        "gsl_title", "other_parts", "is_without_pledge", "is_main_owner",
        "third_parties", "decis_level_id", "ca_decis_level_id",
        "is_legal_exp_launched", "voting_fm_id", "voting_km_id",
        "is_legal_exp_restart", "scp_gsl_name_str", "pricing_id",
        "price_calc_completed", "resp_cond_coord", "curator_head_id",
        "is_lspr_level", "collateral_cont_id", "clc_grade_id",
        "scp_arm_manager_id", "scp_proc_steds_id", "is_auto_sec_errors",
        "is_auto_check_errors", "is_na_active", "reason_refusal_id",
        "is_form_bch_active", "is_bch_validator_on", "suz_start_page_str",
        "is_active_get_arbitr", "scp_cheif_cm_id", "scp_rejection_comment",
        "scp_rejection_client_id", "ca_rout_office_id", "is_test",
        "client_list_changed", "tranche_term", "is_app_to_cred_depart",
        "scp_type_restruct_id", "is_need_agr_cd_co", "is_ca_notif",
        "scp_bg_owner_lidm", "is_check_list_cont_dev", "is_active_get_dp",
        "scp_bg_current_gr_limit", "scp_bg_total_prod_limit",
        "is_min_level_changed", "interm_file_storage",
        "is_proj_verif_finished", "gsl_data_cont_id", "industry_code_id",
        "is_cov_bank_garant", "scp_product_str", "is_state_program",
        "cred_technology_str", "is_not_red_zona_bool", "is_not_red_zone",
        "is_fin_activ_newsub", "prelim_gsl_calc_id",
    ]
    batch_insert(cur, "scp_application", cols, rows, desc="scp_application")
    reg.scp_application = list(range(1, n + 1))


def seed_ic_application(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        base = _application_base(i)
        rows.append(base + (
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), round(random.uniform(100000, 50000000), 2),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random.choice([0, 1]),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random.choice([0, 1]),
            f"ГСЛ {i}", random.choice([0, 1]),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), fake.text(max_nb_chars=200),
            random.choice([0, 1]), None,
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "afl_doc_num", "afl_doc_data", "afp_state_id", "initiator_id",
        "emp_id", "processing_steps_id", "temp_cont_turn", "cr_id",
        "scp_tech_ctredit", "scp_business_segment", "client_type_id",
        "gsl_data_cont_id", "scp_arm_manager_id", "req_type_id",
        "credit_logic_id", "gsl_limit", "pricing_id", "scp_gsl_name_str",
        "resp_cond_coord", "curator_head_id", "resp_cond_coord_str",
        "is_auto_creation", "industry_code_id", "app_obj_id",
        "deleg_region_id", "scp_proc_steds_id", "is_directed_to_process",
        "scp_product_str", "is_state_program", "cred_technology_str",
        "is_na_active", "is_fin_activ_newsub", "prelim_gsl_calc_id",
        "scp_rejection_client_id", "reason_refusal_id", "is_ic_withdrawn",
        "scp_rejection_comment", "is_button_refuse",
    ]
    batch_insert(cur, "ic_application", cols, rows, desc="ic_application")
    reg.ic_application = list(range(1, n + 1))


def seed_corp_tech_application(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        base = _application_base(i)
        rows.append(base + (
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            round(random.uniform(100000, 50000000), 2),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random.randint(6, 60),
            random_bigint_id(1000), round(random.uniform(100000, 50000000), 2),
            fake.text(max_nb_chars=200), random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(1000), random.choice([0, 1]),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), random_bigint_id(1000),
            f"ГСЛ {i}", random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(1000), random_bigint_id(1000),
            fake.text(max_nb_chars=300), random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random.choice([0, 1]),
            random.choice([0, 1]), random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(1000), random.choice([0, 1]),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(1000), random_datetime(),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            random.choice([0, 1]), fake.text(max_nb_chars=200),
            random_bigint_id(1000), fake.text(max_nb_chars=200),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(1000), random.choice([0, 1]),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(1000), random.choice([0, 1]),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(1000), f"Продукт {i}",
            random.choice([0, 1]), f"Технология {i}",
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random.choice([0, 1]), None,
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "afl_doc_num", "afl_doc_data", "afp_state_id", "initiator_id",
        "emp_id", "processing_steps_id", "temp_cont_turn", "cr_id",
        "scp_tech_ctredit", "scp_business_segment", "client_type_id",
        "is_without_pledge", "lim_currency_id", "req_type_id",
        "credit_logic_id", "gsl_limit", "is_main_owner", "risk_zone_id",
        "scp_arm_manager_id", "loan_terms", "auto_check_status", "lim_sum",
        "third_parties", "scp_proc_steds_id", "is_active_get_gsl_part",
        "is_na_active", "deleg_region_id", "client_list_changed",
        "gsl_data_cont_id", "scp_gsl_name_str", "ca_rout_office_id",
        "is_form_bch_active", "is_active_exp_sec", "scp_hcm_decision_id",
        "scp_appl_type_id", "comment_txt", "sec_conclusion_id",
        "is_bch_validator_on", "industry_code_id", "scp_product_str",
        "is_state_program", "cred_technology_str", "is_auto_check_errors",
        "scp_type_restruct_id", "interm_file_storage", "suz_start_page_str",
        "is_legal_exp_launched", "is_legal_exp_restart",
        "scp_cheif_cm_id", "collat_initiator_id", "is_return_awp",
        "iniciator_emp_id", "scp_rejection_client_id",
        "is_app_to_cred_depart", "scp_rejection_comment",
        "reason_refusal_id", "cred_depart_opinion_txt", "is_start_bp_fa",
        "is_start_bp_request_fa", "is_simplified_fa",
        "is_tech_ham_task_comp", "is_auto_sec_errors", "pricing_id",
        "calc_risk_date", "collateral_cont_id", "resp_cond_coord",
        "is_fin_activ_newsub", "prelim_gsl_calc_id", "exp_fa_office_id",
        "scp_conclusion_comment",
    ]
    batch_insert(cur, "corp_tech_application", cols, rows, desc="corp_tech_application")
    reg.corp_tech_application = list(range(1, n + 1))


def seed_mler_application(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        base = _application_base(i)
        rows.append(base + (
            round(random.uniform(100000, 50000000), 2),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), f"Клиент {i}",
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_datetime(),
            f"AMD-{i:07d}", random_bigint_id(1000),
            round(random.uniform(100000, 50000000), 2),
            random.randint(6, 60), random.choice([0, 1]),
            random_datetime(), random_bigint_id(1000),
            fake.text(max_nb_chars=200), random.choice([0, 1]),
            random.choice([0, 1]), f"ГСЛ {i}",
            random_bigint_id(1000), random_bigint_id(1000),
            f"Продукт {i}", random.choice([0, 1]),
            f"Технология {i}", random_bigint_id(1000),
            random.choice([0, 1]), None,
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "afl_doc_num", "afl_doc_data", "afp_state_id", "initiator_id",
        "emp_id", "processing_steps_id", "temp_cont_turn", "cr_id",
        "scp_tech_ctredit", "scp_business_segment", "client_type_id",
        "lim_sum", "gsl_data_cont_id", "scp_cheif_cm_id", "mler_decis_id",
        "mler_client_name", "is_out_app", "chief_initiator_id",
        "req_type_id", "execut_admin_id", "mler_signer_id",
        "client_section_id", "project_decis_id", "date_amd_decision",
        "num_amd_decision", "credit_logic_id", "gsl_limit", "loan_terms",
        "decis_use_limit", "signed_risks_date", "deleg_region_id",
        "decis_use_limit_text", "is_decision_signed",
        "is_decision_approved", "scp_gsl_name_str", "scp_proc_steds_id",
        "industry_code_id", "scp_product_str", "is_state_program",
        "cred_technology_str", "app_product_id", "is_fin_activ_newsub",
        "prelim_gsl_calc_id",
    ]
    batch_insert(cur, "mler_application", cols, rows, desc="mler_application")
    reg.mler_application = list(range(1, n + 1))


# ---------------------------------------------------------------------------
# LAYER 4: ЭКСПЕРТИЗЫ, ПРОЕКТЫ РЕШЕНИЙ, ЗАЛОГИ
# ---------------------------------------------------------------------------
def seed_scp_sec_expertise(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"СЭБ {i}", f"SEB {i}", f"Security Expertise {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, f"DOC-SEB-{i:07d}", random_datetime(),
            random_bigint_id(1000), random_bigint_id(1000),
            random_datetime(2025, 2027), random_bigint_id(1000),
            random_bigint_id(1000), random.choice([0, 1]),
            random.choice([0, 1]), fake.text(max_nb_chars=100),
            random_datetime(), random.choice([0, 1]),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random_datetime(),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            f"SEB_{i:07d}", random_datetime(2025, 2027),
            random_datetime(2025, 2027),
            fake.text(max_nb_chars=100), fake.text(max_nb_chars=100),
            fake.text(max_nb_chars=100), None, random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_datetime(),
            random_bigint_id(1000),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "afl_doc_num", "afl_doc_data", "afp_state_id", "emp_id",
        "sec_end_date", "expertise_obj_id", "risk_zone_id", "is_appeal",
        "is_special_inform", "sec_recall_reason", "sec_date_check",
        "is_ses_withdrawn", "reg_resp_emp", "scp_application_id",
        "is_region_work", "start_sec_date", "dataminer_in_process",
        "sf_app_obj_id", "traf_lights_response_id", "ident",
        "sf_exp_term_date", "end_date", "reason_revision_str",
        "reason_restart_str", "reason_cancel_str", "sec_exp_copy_id",
        "deleg_region_id", "is_company_state_top", "app_obj_id",
        "ct_sec_check_res_id", "psb_office_id", "csd_expertise_obj_id",
        "print_form_date", "deleg_emp_id",
    ]
    batch_insert(cur, "scp_sec_expertise", cols, rows, desc="scp_sec_expertise")
    reg.scp_sec_expertise = list(range(1, n + 1))


def seed_scp_sec_check_res(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Результат {i}", f"Result {i}", f"Check Result {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, random_bigint_id(1000),
            random_datetime(), random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), f"Роли {i}",
            fake.text(max_nb_chars=200), fake.text(max_nb_chars=200),
            fake.text(max_nb_chars=200), fake.text(max_nb_chars=200),
            f"Аффилированные: {fake.company()}",
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), fake.text(max_nb_chars=200),
            fake.text(max_nb_chars=200), random_bigint_id(1000),
            fake.text(max_nb_chars=300), fake.text(max_nb_chars=300),
            fake.text(max_nb_chars=300), fake.text(max_nb_chars=300),
            fake.text(max_nb_chars=300), fake.text(max_nb_chars=300),
            fake.text(max_nb_chars=300),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "expertise_obj_id", "sec_date_check", "emp_id", "tech_atr_bool",
        "check_completed", "is_hide_check_manual", "scp_cl_role_str",
        "other_comment", "settle_accounts_comm", "family_status_comm",
        "credit_history_comm", "affil_client_str", "aspr_link_zone_id",
        "aspr_zone_id", "aspr_affil_res_id", "aspr_route_id",
        "bch_mem_res_id", "aspr_cred_hist_comm", "affil_check_comm",
        "supp_check_res_id", "sf_family_status_comm",
        "sf_settle_accounts_comm", "sf_credit_history_comm",
        "sf_other_comment", "sf_affil_client_str", "sf_affil_check_comm",
    ]
    batch_insert(cur, "scp_sec_check_res", cols, rows, desc="scp_sec_check_res")
    reg.scp_sec_check_res = list(range(1, n + 1))


def seed_scp_part_sec_expertise(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"СЭБ уч. {i}", f"Part SEB {i}", f"Part SEB {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, f"DOC-PSEB-{i:07d}", random_datetime(),
            random_bigint_id(1000), random_bigint_id(1000),
            random_datetime(), fake.text(max_nb_chars=100),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random.choice([0, 1]),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(1000), random_datetime(),
            random_bigint_id(1000), f"PSEB_{i:07d}",
            random_datetime(2025, 2027), random_datetime(2025, 2027),
            fake.text(max_nb_chars=100), fake.text(max_nb_chars=100),
            fake.text(max_nb_chars=100), None,
            random_bigint_id(1000),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "afl_doc_num", "afl_doc_data", "afp_state_id", "emp_id",
        "sec_date_check", "revoke_reason", "expertise_obj_id",
        "deleg_region_id", "risk_zone_id", "sec_expertise_id",
        "sec_ch_res_list", "ses_resp_user_id", "check_completed",
        "ses_conf_user_id", "check_button_vis", "repeat_check",
        "finish_task_date", "psb_office_id", "sec_check_auto_date",
        "ident", "sf_exp_term_date", "end_date", "reason_revision_str",
        "reason_restart_str", "reason_cancel_str", "csd_expertise_obj_id",
        "sf_sec_rs_emp_id",
    ]
    batch_insert(cur, "scp_part_sec_expertise", cols, rows, desc="scp_part_sec_expertise")
    reg.scp_part_sec_expertise = list(range(1, n + 1))


def seed_scp_collateral_app(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Залог {i}", f"Coll {i}", f"Collateral {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            f"SUZ_{i:07d}", random_bigint_id(1000),
            random_bigint_id(1000),
            f"{fake.city()}, ул. {fake.street_name()}, д. {random.randint(1,100)}",
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000),
            round(random.uniform(100_000, 100_000_000), 2),
            round(random.uniform(100_000, 100_000_000), 2),
            round(random.uniform(100_000, 100_000_000), 2),
            f"Объект залога {i}", random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), round(random.uniform(0.1, 0.5), 2),
            round(random.uniform(0.5, 1.5), 2), random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), None, round(random.uniform(0.01, 1), 2),
            random.choice([0, 1]), fake.text(max_nb_chars=300),
            random_bigint_id(1000), random.choice([0, 1]),
            random_datetime(), random_datetime(2025, 2030),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random.randint(1, 10),
            random_bigint_id(1000), random_bigint_id(1000),
            fake.text(max_nb_chars=200), random.choice([0, 1]),
            fake.address(), round(random.uniform(100_000, 50_000_000), 2),
            random_bigint_id(1000),
            round(random.uniform(100_000, 50_000_000), 2),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), fake.text(max_nb_chars=200),
            f"http://suz/{i}", random_datetime(),
            random_bigint_id(1000), random_bigint_id(1000),
            random.randint(1, 100),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "app_obj_id", "exp_obj_id", "out_collateral_id", "collateral_link",
        "coll_appl_type_id", "na_pledge_type_id", "pledge_addr_str",
        "security_quality_id", "quality_group_id", "liquidity_level_id",
        "attr_market_val", "attr_fair_val", "attr_collateral_val",
        "collat_obj_name", "emp_id", "ca_exp_emp_id", "cur_upd_appl_id",
        "parent_collat_app_id", "collateral_discount", "discount_rate",
        "appl_state_id", "is_pres_spouse_cons", "is_pres_guar_pled",
        "necessity_insurance", "subs_pledge_id", "total_struct_share",
        "is_current_concl", "conclus_txt", "pledge_concl_state_id",
        "is_export_suz", "pledge_conclus_date", "concl_validity_date",
        "perform_hr_face_id", "pledge_subject_id", "collat_common_obj_id",
        "collat_subj_count", "scp_arm_chief_id", "cp_arm_manager_id",
        "scp_info_comment_txt", "scp_info_proj_fin", "scp_info_adress_str",
        "scp_info_sec_cost", "scp_info_type_na_id", "scp_info_cred_summ",
        "scp_info_type_prod_id", "scp_info_pledger_id",
        "scp_project_fin_id", "scp_fin_proj_id", "scp_quest_dec_id",
        "add_comm_concl_txt", "coll_link_str", "scp_file_req_timest",
        "scp_info_vnd_id", "quest_decis_id", "testnumber",
    ]
    batch_insert(cur, "scp_collateral_app", cols, rows, desc="scp_collateral_app")
    reg.scp_collateral_app = list(range(1, n + 1))


def seed_scp_decision_quest(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Вопрос {i}", f"Quest {i}", f"Decision Quest {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, random_bigint_id(1000),
            round(random.uniform(100000, 50000000), 2),
            random_bigint_id(1000), random_bigint_id(1000),
            random.randint(6, 60), random_bigint_id(1000),
            random_bigint_id(1000), fake.text(max_nb_chars=300),
            fake.text(max_nb_chars=500), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000),
            round(random.uniform(100000, 50000000), 2),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(1000), random.choice([0, 1]),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000), i,
            random_bigint_id(1000),
            round(random.uniform(100000, 50000000), 2),
            f"Продукт + состав {i}", random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), f"PROD-{i:06d}",
            random.choice([0, 1]), random_bigint_id(1000),
            round(random.uniform(100000, 50000000), 2),
            f"SL-{i:06d}", random.choice([0, 1]),
            random_bigint_id(1000), random.choice([0, 1]),
            random_bigint_id(1000),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "app_obj_id", "scp_sublimit_sum", "scp_sublimit_purpose",
        "app_product_id", "scp_sublimit_srok", "scp_sublimit_val",
        "scp_subl_bor", "annotation", "question_structure",
        "scp_dec_quest_id", "scp_gov_program_id", "source_financing_id",
        "credit_purpose_id", "est_credit_limit", "is_inactive",
        "is_state_program", "type_loan_id", "is_afhd", "rate_type_id",
        "product_compound_id", "amdp_parent_product_id", "scp_state_id",
        "scp_project_ans_link", "is_product_recalc", "ord", "sys_file_id",
        "appr_sum", "product_compound_str", "loan_type_id",
        "part_excl_ship_debitor", "attr_business_segment", "scp_num_subl",
        "sublimit_sum", "subl_num", "is_ca_change_class",
        "credit_report_class", "tech_atr_bool", "copy_source_quest_id",
    ]
    batch_insert(cur, "scp_decision_quest", cols, rows, desc="scp_decision_quest")
    reg.scp_decision_quest = list(range(1, n + 1))


def seed_scp_project_ans(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Проект {i}", f"Project {i}", f"Project Ans {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), f"PRJ-{i:07d}", random_datetime(),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), f"OKPD_{i:05d}",
            round(random.uniform(100000, 50000000), 2),
            round(random.uniform(100000, 50000000), 2),
            round(random.uniform(100000, 50000000), 2),
            round(random.uniform(100000, 50000000), 2),
            round(random.uniform(100000, 50000000), 2),
            random_bigint_id(1000), random_bigint_id(1000),
            round(random.uniform(100000, 50000000), 2),
            random.randint(6, 60),
            round(random.uniform(100000, 10000000), 2),
            random.randint(6, 60),
            round(random.uniform(10000, 1000000), 2),
            round(random.uniform(100000, 50000000), 2),
            random_bigint_id(1000), fake.text(max_nb_chars=200),
            round(random.uniform(0.5, 5), 2), random_bigint_id(1000),
            round(random.uniform(100000, 50000000), 2),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            round(random.uniform(100000, 50000000), 2),
            random_bigint_id(1000), random_bigint_id(1000),
            round(random.uniform(100000, 100000000), 2),
            round(random.uniform(100000, 100000000), 2),
            round(random.uniform(100000, 100000000), 2),
            round(random.uniform(100000, 100000000), 2),
            random_bigint_id(1000), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), random.choice([0, 1]),
            round(random.uniform(0, 100), 2), round(random.uniform(0, 100), 2),
            random_bigint_id(1000), random_bigint_id(1000),
            random.choice([0, 1]), fake.text(max_nb_chars=100),
            fake.text(max_nb_chars=200), fake.text(max_nb_chars=200),
            fake.text(max_nb_chars=200), f"CD-{i:06d}",
            fake.text(max_nb_chars=200), random_bigint_id(1000),
            random_bigint_id(1000), f"DL-{i:06d}", random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            random.choice([0, 1]), random_bigint_id(1000),
            round(random.uniform(100000, 50000000), 2),
            round(random.uniform(100000, 50000000), 2),
            random_bigint_id(1000), random_bigint_id(1000),
            round(random.uniform(100000, 100000000), 2),
            fake.text(max_nb_chars=300), f"LC-{i:06d}",
            fake.city(), random.choice([0, 1]), random_bigint_id(1000),
            random.choice([0, 1]), fake.text(max_nb_chars=100),
            fake.text(max_nb_chars=100), fake.text(max_nb_chars=100),
            random.choice([0, 1]), random_datetime(2025, 2030),
            random_datetime(2025, 2030), random_bigint_id(1000),
            round(random.uniform(5, 30), 2), round(random.uniform(1, 15), 2),
            round(random.uniform(5, 30), 2), random.choice([0, 1]),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "req_link_id", "question_link_id", "voting_km_id", "voting_fm_id",
        "draft_decision_id", "urm_undwrt_decision_id", "decis_level_id",
        "doc_num", "doc_data", "is_under_3_years_exp", "scp_loan_sign_id",
        "loan_sign_st_ot_id", "okpd2", "curret_limit_gsl", "new_limit_gsl",
        "current_limit_borow", "new_limit_borow", "set_matrix_limit",
        "real_estate_class_id", "loan_type_id", "amount_rub",
        "credit_line_term", "summ_tranche", "tranche_term",
        "monthly_contribution", "payment_delay_months", "amount_blanc_deal",
        "blanc_deal_asmt_result", "individual_repay_sched",
        "rate_increase_blanc", "repayment_type_id", "susp_cond_prev_id",
        "curator_head_id", "resp_head_cm_id", "credit_analyst_id",
        "is_infinite_vkl", "is_blanc_credit", "exp_limit_credit_rub",
        "refer_empl", "spec_fa", "attr_market_val", "attr_fair_val",
        "product_security", "attr_collateral_val", "collateral_monit",
        "limit_confirmation", "amdp_parent_product_id", "scp_state_id",
        "rm_ra_decis_level_id", "voting_rm_id", "plan_deal_date",
        "is_active_pj", "okved_activity_id", "is_poci_active",
        "mon_col_type_id", "prod_sec", "el_individual", "clc_grade_id",
        "resp_risk_manager_id", "cancel_manage_desic", "cancel_manag_desic",
        "undwrit_appl_id", "is_refresh_state", "industry_code_id",
        "scp_subl_bor", "client_type_id", "gsl_comparison", "clc_zone_id",
        "restruct_init_id", "monit_viol_txt", "analys_res_cl_txt",
        "analys_res_cl_restr_id", "deal_change_txt", "changed_decision_num",
        "deal_change_restr_txt", "scp_type_restruct_id",
        "min_decis_level_id", "modif_num_deals", "scp_matrix_type",
        "is_need_agr_cd_co", "state_id", "is_old_visual_needed",
        "change_initiator_id", "scp_is_individual", "lidm_cur_limit",
        "lidm_cur_limit_new", "scp_bg_owner_lidm", "scp_chief_ca_id",
        "total_looped_sum", "gsl_compare_txt", "limit_confirm_str",
        "proj_city_str", "is_primary_preparation", "req_type_id",
        "is_cov_bank_garant", "memo_deal_log", "ns_deal_cond_log",
        "confirm_cred_limit_log", "confirm_csd_log", "limit_due_date",
        "limit_review_date", "credit_group_id", "raroc_roe",
        "weighted_margin", "raroc_perc", "is_risk_consideration",
    ]
    batch_insert(cur, "scp_project_ans", cols, rows, desc="scp_project_ans")
    reg.scp_project_ans = list(range(1, n + 1))


# ---------------------------------------------------------------------------
# LAYER 5: ПРОДУКТЫ, ЦЕНЫ, УАиГ
# ---------------------------------------------------------------------------
def seed_scp_amd_product(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"РУМ продукт {i}", f"RUM Product {i}", f"AMD Product {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
            round(random.uniform(100000, 50000000), 2),
            random_bigint_id(n), random.randint(6, 60),
            random.randint(30, 365), random_bigint_id(n),
            random_bigint_id(n), random.choice([0, 1]),
            random_bigint_id(n), random.choice([0, 1]),
            round(random.uniform(10000, 1000000), 2),
            random_bigint_id(n), random.randint(1, 60),
            random_bigint_id(n),
            round(random.uniform(100000, 50000000), 2),
            round(random.uniform(100000, 50000000), 2),
            round(random.uniform(100000, 50000000), 2),
            random.choice([0, 1]), random_bigint_id(n),
            random.choice([0, 1]), random_bigint_id(n),
            random.choice([0, 1]), random_bigint_id(n),
            random.choice([0, 1]), random.choice([0, 1]),
            random_bigint_id(n), random_bigint_id(n),
            round(random.uniform(100000, 50000000), 2),
            round(random.uniform(0, 100), 2), random_bigint_id(n),
            f"VIOL_{i}", f"SUB_{i}", random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
            round(random.uniform(100000, 50000000), 2),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_datetime(),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), fake.text(max_nb_chars=300),
            random.choice([0, 1]),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "app_product_id", "loan_type_id", "scp_sublimit_val",
        "scp_general_amount", "amdp_parent_product_id", "product_term",
        "product_limitation", "product_compound_id", "type_gov_prog_id",
        "is_inactive", "blanc_deal_asmt_result", "is_blanc_credit",
        "monthly_contribution", "loan_type_afhd_id", "repayment_type_id",
        "rate_increase_blanc", "amount_blanc_deal", "amount_blanc_deal_clt",
        "allowed_blanc_amo_prod", "is_contract_logic_p", "draft_dec_id",
        "is_oth_bank_guar_psb", "contr_cont_id", "is_add_req_bank_guar",
        "security_part_id", "is_requirements_meets", "is_sdo",
        "comp_type_gov_prog_id", "clc_grade_id", "exp_limit_credit_rub",
        "el_individual", "clc_zone_id", "ident_viol_req",
        "seq_subproduct_numb", "scp_loan_sign", "borr_restr_seq_num",
        "curr_loan_debt", "amount_loan_debt", "product_risk_asses_id",
        "test_amd_proj_link", "scp_prod_quest_id", "amd_proj_link",
        "prod_term_date", "scp_loan_sign_id", "amd_prod_link_id",
        "cl_group_id", "question_structure", "is_over_limit",
    ]
    batch_insert(cur, "scp_amd_product", cols, rows, desc="scp_amd_product")
    reg.scp_amd_product = list(range(1, n + 1))


def seed_product_pricing(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"ЦО {i}", f"Pricing {i}", f"Pricing {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, random_bigint_id(n),
            random_bigint_id(n), random.choice([0, 1]),
            round(random.uniform(5, 25), 2),
            round(random.uniform(1, 10), 2),
            round(random.uniform(2, 15), 2), random_bigint_id(n),
            random.randint(6, 60),
            round(random.uniform(100000, 50000000), 2),
            random_bigint_id(n), random.choice([0, 1]),
            random_bigint_id(n), random.choice([0, 1]),
            random.randint(6, 60), random.randint(30, 365),
            round(random.uniform(0.5, 5), 2),
            round(random.uniform(100000, 10000000), 2),
            fake.text(max_nb_chars=200), fake.text(max_nb_chars=200),
            round(random.uniform(1, 10), 2), random.randint(30, 365),
            random_bigint_id(n), random_bigint_id(n),
            round(random.uniform(0, 100), 2), random.choice([0, 1]),
            round(random.uniform(100000, 10000000), 2),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n),
            round(random.uniform(100000, 50000000), 2),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
            round(random.uniform(1, 10), 2),
            round(random.uniform(1, 10), 2),
            round(random.uniform(1, 10), 2),
            round(random.uniform(1, 10), 2),
            round(random.uniform(5, 25), 2),
            round(random.uniform(5, 25), 2),
            random.choice([0, 1]), round(random.uniform(1, 10), 2),
            round(random.uniform(1, 10), 2),
            round(random.uniform(1, 10), 2),
            round(random.uniform(0.5, 3), 2), random_bigint_id(n),
            random_bigint_id(n), random.choice([0, 1]),
            round(random.uniform(100000, 50000000), 2),
            random.choice([0, 1]), random_bigint_id(n),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "pricing_card_id", "owner_object_id", "scp_is_individual",
        "scp_calc_rate_val", "scp_min_margin_val", "offer_margin_over",
        "rate_type_id", "scp_sublimit_srok", "scp_sublimit_sum",
        "draft_decision_id", "is_inactive", "product_pricing_id",
        "is_state_program", "tranche_term", "tranche_term_days",
        "g_rate_principal", "cr_amount", "tender_guarantees",
        "execution_guarantee", "scp_min_insec_margin", "term_days",
        "pay_reward_cond_id", "amdp_parent_product_id", "el_individual",
        "is_param_calc", "cr_limit_guar", "clc_grade_id",
        "pricing_compare_id", "scp_modif_lim_quest_id", "clc_zone_id",
        "scp_sublimit_sum_prev", "gsl_limit", "type_loan_id",
        "app_product_id", "product_compound_id", "scp_min_margin_from",
        "scp_min_margin", "min_insec_margin_from", "min_insec_margin_to",
        "scp_calc_rate_val_from", "scp_calc_rate_val_to", "is_marge_range",
        "scp_min_margin_val_from", "offer_margin_over_from",
        "offer_margin_over_to", "fix_spread_value", "change_initiator_id",
        "product_pricing_cast_id", "is_out_app", "sublimit_sum",
        "is_umb_surety", "cl_group_id",
    ]
    batch_insert(cur, "product_pricing", cols, rows, desc="product_pricing")
    reg.product_pricing = list(range(1, n + 1))


def seed_prod_change_params(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Параметр {i}", f"Param {i}", f"Param {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, random_bigint_id(n),
            random_bigint_id(n), f"{round(random.uniform(5, 20), 2)}%",
            f"{random.randint(10000, 1000000)} руб.",
            f"{round(random.uniform(5, 20), 2)}%",
            f"{random.randint(10000, 1000000)} руб.",
            fake.text(max_nb_chars=100), random_bigint_id(n),
            round(random.uniform(0.5, 5), 2), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random.randint(1000, 500000),
            random.randint(1000, 500000), random_bigint_id(n),
            round(random.uniform(0.5, 5), 2),
            f"{round(random.uniform(0.5, 5), 2)}%",
            f"{round(random.uniform(0.5, 5), 2)}%",
            random.choice([0, 1]), random.choice([0, 1]),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "product_pricing_id", "change_param_dict_id", "scp_new_cond",
        "scp_old_cond_val", "scp_old_cond", "scp_new_cond_val",
        "value_comment", "link_card_obj_id", "com_val_proc",
        "payment_schedule_id", "pay_reward_cond_id", "sum_pay_type_id",
        "comm_date_pay_id", "bank_val_sum", "new_bank_val_sum",
        "new_pay_reward_cond_id", "new_com_val_proc",
        "scp_comiss_size_str", "new_comiss_size_str",
        "is_add_manual", "is_auto_creation",
    ]
    batch_insert(cur, "prod_change_params", cols, rows, desc="prod_change_params")
    reg.prod_change_params = list(range(1, n + 1))


def seed_prod_commissions(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Комиссия {i}", f"Comm {i}", f"Commission {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, random_bigint_id(n),
            f"{round(random.uniform(0.1, 3), 2)}%", "Ежемесячно",
            round(random.uniform(0.1, 5), 2), fake.text(max_nb_chars=100),
            random_bigint_id(n), random.choice([0, 1]),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random.choice([0, 1]),
            random.choice([0, 1]), random.choice([0, 1]),
            random.choice([0, 1]), random.randint(100, 100000),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "prod_comm_dict_id", "scp_comiss_size_str",
        "scp_payment_shedule_str", "com_val_proc", "value_comment",
        "link_card_obj_id", "is_for_state_program", "comm_date_pay_id",
        "sum_pay_type_id", "payment_schedule_id", "is_from_pricing",
        "is_add_manual", "is_current_conds", "commission_out_of_dict",
        "bank_val_sum",
    ]
    batch_insert(cur, "prod_commissions", cols, rows, desc="prod_commissions")
    reg.prod_commissions = list(range(1, n + 1))


def seed_prod_guarantees(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Гарантия {i}", f"Guarantee {i}", f"Guarantee {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, random_bigint_id(n),
            random_bigint_id(n), round(random.uniform(0.5, 3), 2),
            random.randint(10000, 1000000), random_bigint_id(n),
            random.choice([0, 1]), random.choice([0, 1]),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "link_card_obj_id", "prod_guarant_dict_id", "bank_val_proc",
        "bank_val_sum", "guarantee_type_id", "is_from_pricing",
        "is_current_conds",
    ]
    batch_insert(cur, "prod_guarantees", cols, rows, desc="prod_guarantees")
    reg.prod_guarantees = list(range(1, n + 1))


def seed_sys_obj_resp(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"Resp {i}", f"Ответств. {i}", f"Ответств. {i}",
            random_datetime(), 2, 1, 1, 1, random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n), 1, 1, 1,
            random_datetime(), 0, random_bigint_id(n),
            fake.text(max_nb_chars=100), f"Org {i}",
            random_datetime(), random_datetime(2025, 2030),
            random_bigint_id(n), random_bigint_id(n),
        ))
    cols = [
        "id", "name__en", "name__ru", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "afe_emp_id", "afe_obj_id",
        "afe_subject_id", "created_emp_id", "last_modified_user_id",
        "last_modified_emp_id", "last_modified_date", "is_system",
        "afe_ext_obj_id", "afe_resp_comment", "afe_short_name",
        "afe_start_stamp", "afe_end_stamp", "afe_current_resp",
        "afe_manage_emp",
    ]
    batch_insert(cur, "sys_obj_resp", cols, rows, desc="sys_obj_resp")
    reg.sys_obj_resp = list(range(1, n + 1))


def seed_scp_dict_product_na(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        rows.append((
            i, f"НА продукт {i}", f"NA Product {i}", f"NA Product {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, i, f"NAP_{i:05d}",
            f"Group_{i}", f"Prog_{i}", random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "ord", "ident", "contract_group", "credit_product",
        "app_product_id", "yaig_product_id", "contr_group_id",
    ]
    batch_insert(cur, "scp_dict_product_na", cols, rows, desc="scp_dict_product_na")
    reg.scp_dict_product_na = list(range(1, n + 1))


def seed_yaig_client_gen_agr(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        open_dt = random_datetime(2018, 2024)
        close_dt = open_dt + timedelta(days=random.randint(365, 365 * 5))
        rows.append((
            i, f"ГС {i}", f"GA {i}", f"Gen Agr {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, random_bigint_id(n), i,
            round(random.uniform(1_000_000, 500_000_000), 2),
            close_dt, open_dt, f"GA-{i:07d}",
            round(random.uniform(0, 100_000_000), 2),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "yaig_client_princip_id", "yaig_gen_agr_id", "yaig_gen_agr_sum",
        "yaig_date_close", "yaig_date_open", "yaig_gen_agr_num",
        "yaig_unused_limit", "yaig_gen_agr_type_id", "yaig_cur_id",
        "yaig_client_link", "yaig_base_code",
    ]
    batch_insert(cur, "yaig_client_gen_agr", cols, rows, desc="yaig_client_gen_agr")
    reg.yaig_client_gen_agr = list(range(1, n + 1))


def seed_yaig_client_guarantee(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    rows = []
    for i in range(1, n + 1):
        open_dt = random_datetime(2018, 2024)
        close_dt = open_dt + timedelta(days=random.randint(180, 365 * 3))
        rows.append((
            i, f"Гарантия {i}", f"Guarantee {i}", f"Guarantee {i}",
            random_datetime(), 2, 1, 1, 1, random_datetime(), 1, 1, 1,
            random_datetime(), 0, random_bigint_id(n),
            random_bigint_id(n),
            round(random.uniform(100_000, 50_000_000), 2),
            fake.name(), random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
            random_bigint_id(n), random_bigint_id(n),
            close_dt, open_dt, f"GUAR-{i:07d}",
            random_bigint_id(n),
            round(random.uniform(1000, 500000), 2),
            f"MGR_{i:07d}", random_datetime(2025, 2030),
            random.choice([0, 1]), random.randint(0, 10),
            random_bigint_id(n), f"PROT-{i:07d}",
            f"DOC-{i:07d}", random_bigint_id(n),
        ))
    cols = [
        "id", "name__ru", "name__en", "name", "create_date", "type_id",
        "status", "org_id", "user_id", "last_modified_date",
        "last_modified_user_id", "last_modified_emp_id", "created_emp_id",
        "last_modified_emp_id", "is_system",
        "yaig_client_princip_id", "yaig_product_id", "yaig_guar_summ",
        "yaig_manager_name", "yaig_risk_group", "yaig_manager_code",
        "yaig_quality_categ", "yaig_guar_type_id", "yaig_prnt_gen_agr_id",
        "yaig_cur_id", "yaig_client_link", "yaig_date_close",
        "yaig_date_open", "yaig_guar_num", "yaig_guarantee_id",
        "yaig_sum_commis", "yaig_manager_code_str",
        "yaig_guar_disclosure", "yaig_guar_payments_bool",
        "yaig_guar_payment", "contr_group_id", "aggr_protocol_num",
        "appl_documentum_num", "yaig_base_code",
    ]
    batch_insert(cur, "yaig_client_guarantee", cols, rows, desc="yaig_client_guarantee")
    reg.yaig_client_guarantee = list(range(1, n + 1))


# ---------------------------------------------------------------------------
# LAYER 6: MS_* (MultiSelect) таблицы
# ---------------------------------------------------------------------------
MS_TABLES = [
    "ms_0golbfqyrdq4im6jf6ajivwy9",
    "ms_0n8ohjyx7oszo6a47ca9g0s6f",
    "ms_0oc5mpme8nklimjy77sai9gf1",
    "ms_1fd5jp86pabxu9na4knwphvyr",
    "ms_333s6j5jn97srp008gyi3zueo",
    "ms_39qrctc1n8efr9axiukjssgzl",
    "ms_64cm5ded37z58x0fyt5lgvhc7",
    "ms_965j58mgwkpomnuooc29dlq9f",
    "ms_9k60rv4p0oaf3c702f2l1gj77",
    "ms_d1oakp9uq175ak3dbhpzbu81d",
    "ms_dlggiqkhqj46rhq1lrgryim7c",
    "ms_dxsh6488ihf77xmsd43dwby6k",
    "ms_e5lum3lbateqhx8wkgtstxdf9",
]

def seed_ms_tables(cur, reg: IdRegistry, n: int = MIN_ROWS) -> None:
    """Составной PK (id, obj_id)."""
    for tbl in MS_TABLES:
        rows = []
        for i in range(1, n + 1):
            rows.append((i, random_bigint_id(n)))
        cols = ["id", "obj_id"]
        batch_insert(cur, tbl, cols, rows, desc=tbl)


# ---------------------------------------------------------------------------
# ДОПОЛНИТЕЛЬНЫЕ ОБЪЕКТЫ ДЛЯ МОДУЛЯ АУДИТА
# ---------------------------------------------------------------------------
def create_audit_helpers(cur) -> None:
    """Индексы на FK + VIEW с PII для теста DIRECT_SENSITIVE."""
    print("  ↳ создание индексов и audit-вьюх")
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_credit_contract_customer "
        "ON public.credit_contract(link_customer_id);",
        "CREATE INDEX IF NOT EXISTS idx_credit_contract_number "
        "ON public.credit_contract(credit_contract_number);",
        "CREATE INDEX IF NOT EXISTS idx_application_obj_state "
        "ON public.application_obj(afp_state_id);",
        "CREATE INDEX IF NOT EXISTS idx_scp_application_initiator "
        "ON public.scp_application(initiator_id);",
        "CREATE INDEX IF NOT EXISTS idx_sys_company_inn "
        "ON public.sys_company(inn);",
        "CREATE INDEX IF NOT EXISTS idx_sys_employee_email "
        "ON public.sys_employee(email);",
        "CREATE INDEX IF NOT EXISTS idx_count_turnover_owner "
        "ON public.count_turnover(link_cnt_owner);",
    ]
    for sql in indexes:
        cur.execute(sql)

    # VIEW с PII — тестовая цель для DIRECT_SENSITIVE
    cur.execute("""
        CREATE OR REPLACE VIEW public.v_sensitive_clients AS
        SELECT id, name, inn, contact_phone, attr_email
        FROM public.sys_company;
    """)
    # Таблица с "password_hash" — для теста прямого доступа к чувствительным полям
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.sys_user_credentials (
            id bigint PRIMARY KEY,
            user_id bigint NOT NULL,
            login varchar(200) NOT NULL,
            password_hash varchar(500) NOT NULL,
            token varchar(500),
            ssn varchar(50),
            card_number varchar(30),
            create_date timestamp
        );
    """)
    rows = [
        (i, random_bigint_id(MIN_ROWS), f"user_{i}",
         f"sha256${random.getrandbits(256):064x}",
         f"tok_{random.getrandbits(128):032x}",
         f"{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}",
         f"{random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}",
         random_datetime())
        for i in range(1, MIN_ROWS + 1)
    ]
    cols = ["id", "user_id", "login", "password_hash", "token", "ssn",
            "card_number", "create_date"]
    batch_insert(cur, "sys_user_credentials", cols, rows,
                 desc="sys_user_credentials (PII)")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> None:
    print(f"🔌 Подключение к {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    # Отключаем FK-проверки, чтобы порядок не был критичен
    print("🔓 Отключение FK-проверок (session_replication_role = replica)")
    cur.execute("SET session_replication_role = 'replica';")

    reg = IdRegistry()

    print("\n=== LAYER 0: Справочники ===")
    seed_sys_state(cur, reg)
    seed_sys_obj_type(cur, reg)
    seed_business_segment(cur, reg)
    seed_scp_techcred(cur, reg)
    seed_scp_dict_tech_ctredit(cur, reg)
    seed_type_loan(cur, reg)
    seed_dict_div_presence(cur, reg)
    seed_cb_interest_rate(cur, reg)
    seed_tbs_type(cur, reg)
    seed_acc_number(cur, reg)
    seed_scp_gov_program_dict(cur, reg)
    seed_scp_prod_guarant_dict(cur, reg)
    seed_scp_prod_comm_dict(cur, reg)
    seed_scp_prod_guar_dict(cur, reg)
    seed_dict_product(cur, reg)
    seed_offices_psb(cur, reg)
    seed_scp_dict_rsc_office(cur, reg)
    seed_yaig_product_dict(cur, reg)
    seed_sys_algorithm(cur, reg)

    print("\n=== LAYER 1: Базовые сущности ===")
    seed_sys_company(cur, reg)
    seed_sys_employee(cur, reg)
    seed_sys_object(cur, reg)
    seed_fs_file(cur, reg)

    print("\n=== LAYER 2: Бизнес-объекты ===")
    seed_application_obj(cur, reg)
    seed_credit_contract(cur, reg)
    seed_count_turnover(cur, reg)
    seed_afhd_ac_trans_link(cur, reg)
    seed_participant_app(cur, reg)

    print("\n=== LAYER 3: Заявки ===")
    seed_scp_application(cur, reg)
    seed_ic_application(cur, reg)
    seed_corp_tech_application(cur, reg)
    seed_mler_application(cur, reg)

    print("\n=== LAYER 4: Экспертизы и решения ===")
    seed_scp_sec_expertise(cur, reg)
    seed_scp_sec_check_res(cur, reg)
    seed_scp_part_sec_expertise(cur, reg)
    seed_scp_collateral_app(cur, reg)
    seed_scp_decision_quest(cur, reg)
    seed_scp_project_ans(cur, reg)

    print("\n=== LAYER 5: Продукты, цены, УАиГ ===")
    seed_scp_amd_product(cur, reg)
    seed_product_pricing(cur, reg)
    seed_prod_change_params(cur, reg)
    seed_prod_commissions(cur, reg)
    seed_prod_guarantees(cur, reg)
    seed_sys_obj_resp(cur, reg)
    seed_scp_dict_product_na(cur, reg)
    seed_yaig_client_gen_agr(cur, reg)
    seed_yaig_client_guarantee(cur, reg)

    print("\n=== LAYER 6: MultiSelect таблицы ===")
    seed_ms_tables(cur, reg)

    print("\n=== Audit helpers (индексы + PII-вьюхи) ===")
    create_audit_helpers(cur)

    # Возвращаем FK-проверки и коммитим
    cur.execute("SET session_replication_role = 'origin';")
    conn.commit()

    # Итоговая статистика
    cur.execute("""
        SELECT schemaname, relname, n_live_tup
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY n_live_tup DESC;
    """)
    print("\n📊 Статистика по таблицам (top-20):")
    for i, (_, tbl, cnt) in enumerate(cur.fetchall()[:20]):
        print(f"  {tbl:40s} → {cnt:>7,} строк")

    cur.close()
    conn.close()
    print("\n✅ Готово! БД наполнена.")


if __name__ == "__main__":
    main()