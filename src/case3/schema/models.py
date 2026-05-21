"""
@file models.py
@brief Машиночитаемое представление схемы PostgreSQL.

@details
    Эти dataclasses — результат парсинга data_model_sql/data_model.sql
    (см. parser.py). Используются:
      - генератором — как контекст в промпте (DDL + комментарии);
      - schema_link — для эмбеддинга «карточек» таблиц и FK-замыкания;
      - аудитором — для резолва SELECT * → список колонок.

    Сериализуются в schema_catalog.json (см. scripts/build_schema_catalog.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Column:
    """
    @brief Одна колонка таблицы.
    @var name     Имя колонки (напр. "client_id").
    @var type     SQL-тип как в DDL (напр. "character varying(2000)").
    @var comment  Человекочитаемое описание из COMMENT ON COLUMN (или None).
    """
    name: str
    type: str
    comment: str | None = None


@dataclass
class ForeignKey:
    """
    @brief Внешний ключ (в дампе FK закомментированы, но логически заданы).
    @var column      Колонка-источник в текущей таблице.
    @var ref_table   Таблица, на которую ссылаемся.
    @var ref_column  Колонка в целевой таблице (обычно "id").
    """
    column: str
    ref_table: str
    ref_column: str


@dataclass
class Table:
    """
    @brief Таблица: колонки, PK, FK, комментарий.
    @var name          Имя таблицы (напр. "credit_contract").
    @var comment       Описание из COMMENT ON TABLE (очищенное от SysObjType-мусора).
    @var columns       Список колонок в порядке объявления.
    @var primary_key   Список колонок PK (обычно ["id"]).
    @var foreign_keys  Список внешних ключей.
    """
    name: str
    comment: str | None = None
    columns: list[Column] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)

    ##
    # @brief Имена колонок списком (удобно для проверок).
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    ##
    # @brief Текстовая «карточка» таблицы для эмбеддинга (schema linking).
    # @details
    #   Склеивает имя + описание + колонки с комментариями в один текст.
    #   Именно его эмбеддит schema_link (ADR-0003, шаг 2).
    def to_card(self) -> str:
        head = f"{self.name}: {self.comment or ''}".strip()
        cols = ", ".join(
            f"{c.name} ({c.comment})" if c.comment else c.name
            for c in self.columns
        )
        return f"{head}\nКолонки: {cols}"

    ##
    # @brief DDL-фрагмент для подачи в промпт генератора (Code Representation).
    def to_ddl(self) -> str:
        lines = [f"-- {self.name}: {self.comment or ''}".rstrip()]
        lines.append(f"CREATE TABLE {self.name} (")
        col_lines = []
        for c in self.columns:
            comm = f"  -- {c.comment}" if c.comment else ""
            col_lines.append(f"    {c.name} {c.type},{comm}")
        # убираем висячую запятую у последней колонки
        if col_lines:
            col_lines[-1] = col_lines[-1].replace(",  --", "  --", 1)
            if col_lines[-1].rstrip().endswith(","):
                col_lines[-1] = col_lines[-1].rstrip()[:-1]
        lines.extend(col_lines)
        lines.append(");")
        if self.foreign_keys:
            for fk in self.foreign_keys:
                lines.append(
                    f"-- foreign key: {self.name}.{fk.column} -> "
                    f"{fk.ref_table}.{fk.ref_column}"
                )
        return "\n".join(lines)


@dataclass
class SchemaCatalog:
    """
    @brief Весь каталог схемы — список таблиц + быстрый индекс по имени.
    """
    tables: list[Table] = field(default_factory=list)

    ##
    # @brief Таблица по имени или None.
    def get(self, name: str) -> Table | None:
        for t in self.tables:
            if t.name == name:
                return t
        return None

    ##
    # @brief FK-замыкание: набор таблиц + те, на которые они ссылаются.
    # @param names  Стартовый набор имён таблиц.
    # @return       Расширенный set имён (для schema linking, ADR-0003 шаг 3).
    def fk_closure(self, names: set[str]) -> set[str]:
        result = set(names)
        for name in list(names):
            table = self.get(name)
            if table is None:
                continue
            for fk in table.foreign_keys:
                result.add(fk.ref_table)
        return result

    ##
    # @brief Сводная статистика (для логов и sanity-check).
    def stats(self) -> dict[str, int]:
        return {
            "tables": len(self.tables),
            "columns": sum(len(t.columns) for t in self.tables),
            "tables_with_comment": sum(1 for t in self.tables if t.comment),
            "columns_with_comment": sum(
                1 for t in self.tables for c in t.columns if c.comment
            ),
            "primary_keys": sum(1 for t in self.tables if t.primary_key),
            "foreign_keys": sum(len(t.foreign_keys) for t in self.tables),
        }

    ##
    # @brief Сериализация в dict (для json.dump).
    def to_dict(self) -> dict[str, Any]:
        return {"tables": [asdict(t) for t in self.tables]}

    ##
    # @brief Десериализация из dict (json.load).
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SchemaCatalog":
        tables = []
        for t in data["tables"]:
            cols = [Column(**c) for c in t.get("columns", [])]
            fks = [ForeignKey(**fk) for fk in t.get("foreign_keys", [])]
            tables.append(Table(
                name=t["name"],
                comment=t.get("comment"),
                columns=cols,
                primary_key=t.get("primary_key", []),
                foreign_keys=fks,
            ))
        return cls(tables=tables)
