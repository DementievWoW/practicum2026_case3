"""
@file parser.py
@brief ЗАГЛУШКА парсера DDL.  Реализует роль: «Данные».

@warning ЭТО ЗАГЛУШКА (walking skeleton).
    Возвращает 3 хардкод-таблицы, чтобы сквозной пайплайн работал, пока
    реальный парсер не написан. Реальную реализацию (regex/pglast по
    data_model.sql → 60 таблиц с FK и комментариями) пишет роль «Данные».

    Реальная версия сохранена в git: тег `reference-impl-v1`
        git show reference-impl-v1:src/case3/schema/parser.py

@todo (роль «Данные»):
    1. Распарсить CREATE TABLE → Column[] (имя, тип).
    2. ALTER TABLE ... PRIMARY KEY → primary_key.
    3. (закомментированные) FOREIGN KEY → foreign_keys.
    4. COMMENT ON TABLE/COLUMN → comment (чистка SysObjType/languageSchema).
    Контракт результата фиксирован: SchemaCatalog (см. models.py).
"""

from __future__ import annotations

from .models import Column, ForeignKey, SchemaCatalog, Table


# Минимальный хардкод-набор — чтобы скелет крутился (НЕ реальная схема).
_STUB_TABLES = [
    Table(
        name="credit_contract",
        comment="Кредитный договор",
        columns=[
            Column("id", "bigint", "ID"),
            Column("credit_contract_number", "varchar(100)", "Номер договора"),
            Column("credit_amount", "numeric", "Сумма кредита"),
            Column("status", "smallint", "Статус"),
            Column("org_id", "bigint", "Подразделение"),
        ],
        primary_key=["id"],
        foreign_keys=[ForeignKey("status", "cr_status", "id")],
    ),
    Table(
        name="acc_number",
        comment="ОСВ: Номер счета",
        columns=[
            Column("id", "bigint", "ID"),
            Column("account_name", "varchar(2000)", "Имя счёта"),
            Column("status", "smallint", "Статус"),
        ],
        primary_key=["id"],
        foreign_keys=[],
    ),
    Table(
        name="cr_status",
        comment="Справочник: статус кредита",
        columns=[Column("id", "bigint", "ID"), Column("name", "varchar(200)", "Название")],
        primary_key=["id"],
        foreign_keys=[],
    ),
]


def parse_ddl(text: str) -> SchemaCatalog:
    """
    @brief ЗАГЛУШКА: игнорирует text, возвращает 3 хардкод-таблицы.
    @param text  Содержимое дампа (в заглушке НЕ используется).
    @return SchemaCatalog из 3 заглушечных таблиц.
    @warning Реальный парсинг пишет роль «Данные» (см. шапку файла).
    """
    return SchemaCatalog(tables=[*_STUB_TABLES])


def parse_file(path: str) -> SchemaCatalog:
    """@brief ЗАГЛУШКА: читает файл, но всё равно возвращает stub-каталог."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = ""
    return parse_ddl(text)
