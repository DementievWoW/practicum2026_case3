"""
@file test_schema_models.py
@brief Тесты структур схемы: Column, ForeignKey, Table, SchemaCatalog.

Покрытие: column_names(), to_card(), fk_closure(), to_dict/from_dict round-trip.
"""
from __future__ import annotations

from case3.schema.models import Column, ForeignKey, SchemaCatalog, Table


def _build_catalog() -> SchemaCatalog:
    """Маленький каталог: 3 таблицы, FK credit_contract → cr_status, → acc_number."""
    tables = [
        Table(
            name="credit_contract",
            comment="Договоры кредитов",
            columns=[
                Column("id", "bigint", "идентификатор"),
                Column("status", "smallint", "статус"),
                Column("acc_id", "bigint", "FK на acc_number"),
            ],
            primary_key=["id"],
            foreign_keys=[
                ForeignKey("status", "cr_status", "id"),
                ForeignKey("acc_id", "acc_number", "id"),
            ],
        ),
        Table(
            name="cr_status",
            comment="Справочник статусов",
            columns=[Column("id", "smallint"), Column("name", "varchar")],
            primary_key=["id"],
        ),
        Table(
            name="acc_number",
            comment="Счета",
            columns=[Column("id", "bigint"), Column("number", "varchar", "номер")],
            primary_key=["id"],
        ),
    ]
    return SchemaCatalog(tables=tables)


def _tables_by_name(cat: SchemaCatalog) -> dict[str, Table]:
    """Удобный доступ по имени (в самом каталоге список)."""
    return {t.name: t for t in cat.tables}


class TestColumn:
    def test_column_basic_fields(self):
        c = Column("id", "bigint", "идентификатор")
        assert c.name == "id"
        assert c.type == "bigint"
        assert c.comment == "идентификатор"

    def test_column_comment_optional(self):
        c = Column("name", "varchar")
        assert c.comment is None


class TestTable:
    def test_column_names_returns_list(self):
        cat = _build_catalog()
        names = _tables_by_name(cat)["credit_contract"].column_names()
        assert names == ["id", "status", "acc_id"]

    def test_to_card_contains_table_name_and_comment(self):
        cat = _build_catalog()
        card = _tables_by_name(cat)["credit_contract"].to_card()
        assert "credit_contract" in card
        # комментарий таблицы попадает в карточку
        assert "Договоры" in card or "договор" in card.lower()

    def test_to_card_contains_columns(self):
        cat = _build_catalog()
        card = _tables_by_name(cat)["credit_contract"].to_card()
        for col in ("id", "status", "acc_id"):
            assert col in card


class TestSchemaCatalogFkClosure:
    def test_fk_closure_adds_referenced_tables(self):
        cat = _build_catalog()
        # стартуем с одной таблицы — должны добавиться cr_status и acc_number
        closure = cat.fk_closure({"credit_contract"})
        assert "credit_contract" in closure
        assert "cr_status" in closure
        assert "acc_number" in closure

    def test_fk_closure_idempotent_on_no_fks(self):
        cat = _build_catalog()
        closure = cat.fk_closure({"cr_status"})
        # cr_status сам не имеет FK
        assert closure == {"cr_status"}

    def test_fk_closure_empty_input_empty_output(self):
        cat = _build_catalog()
        assert cat.fk_closure(set()) == set()


class TestSchemaCatalogRoundtrip:
    def test_to_dict_returns_dict(self):
        cat = _build_catalog()
        d = cat.to_dict()
        assert isinstance(d, dict)
        # формат должен содержать таблицы
        keys = set()
        for v in (d.values() if isinstance(d, dict) else []):
            if isinstance(v, dict):
                keys.update(v.keys())
        # минимум — название таблицы где-то фигурирует
        s = repr(d)
        assert "credit_contract" in s

    def test_from_dict_round_trip(self):
        # to_dict → from_dict даёт ту же структуру (с точностью до порядка таблиц)
        cat = _build_catalog()
        d1 = cat.to_dict()
        cat2 = SchemaCatalog.from_dict(d1)
        names1 = {t.name for t in cat.tables}
        names2 = {t.name for t in cat2.tables}
        assert names1 == names2
        # количество колонок на таблицу совпадает
        idx1 = _tables_by_name(cat)
        idx2 = _tables_by_name(cat2)
        for name in names1:
            assert len(idx1[name].columns) == len(idx2[name].columns)
