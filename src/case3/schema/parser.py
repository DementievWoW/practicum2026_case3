"""
@file parser.py
@brief Парсер дампа PostgreSQL (data_model.sql) → SchemaCatalog.

@details
    Дамп GreenData имеет регулярную структуру:
      - CREATE TABLE public.X (...);              — колонки
      - ALTER TABLE ONLY public.X
            ADD CONSTRAINT ... PRIMARY KEY (id);  — активные PK
      - -- ALTER TABLE ONLY public.X
      --     ADD CONSTRAINT ... FOREIGN KEY (col)
      --     REFERENCES public.Y(id);             — ЗАКОММЕНТИРОВАННЫЕ FK
      - COMMENT ON TABLE  public.X      IS '...';
      - COMMENT ON COLUMN public.X.col  IS '...';

    Почему regex, а не pglast:
      1. pglast — GPLv3, этот слой держим чистым (MIT-friendly).
      2. FK закомментированы — pglast их не увидит, а нам они нужны
         для FK-замыкания (schema linking).
      3. Структура дампа простая и регулярная.

    @note Парсер устойчив к закомментированным constraint'ам: ведущие
          "-- " опциональны в regex для PK/FK.
"""

from __future__ import annotations

import re

from .models import Column, ForeignKey, SchemaCatalog, Table


# ── CREATE TABLE public.NAME ( ... );  (тело — нежадно до "\n);")
_RE_CREATE = re.compile(
    r"CREATE TABLE public\.(\w+)\s*\((.*?)\n\);",
    re.DOTALL,
)

# ── PRIMARY KEY (активный или закомментированный)
_RE_PK = re.compile(
    r"(?:--\s*)?ALTER TABLE ONLY public\.(\w+)\s*\n"
    r"\s*(?:--\s*)?ADD CONSTRAINT \S+ PRIMARY KEY \(([^)]+)\)",
)

# ── FOREIGN KEY (активный или закомментированный)
_RE_FK = re.compile(
    r"(?:--\s*)?ALTER TABLE ONLY public\.(\w+)\s*\n"
    r"\s*(?:--\s*)?ADD CONSTRAINT \S+ FOREIGN KEY \(([^)]+)\)\s*"
    r"REFERENCES public\.(\w+)\s*\(([^)]+)\)",
)

# ── COMMENT ON TABLE/COLUMN ('' — экранированная одинарная кавычка)
_RE_COMMENT_TABLE = re.compile(
    r"COMMENT ON TABLE public\.(\w+) IS '((?:[^']|'')*)';",
)
_RE_COMMENT_COLUMN = re.compile(
    r"COMMENT ON COLUMN public\.(\w+)\.(\w+) IS '((?:[^']|'')*)';",
)


def _unescape(s: str) -> str:
    """@brief Возвращает '' → ' (PostgreSQL-эскейп одинарной кавычки)."""
    return s.replace("''", "'").strip()


def _clean_table_comment(raw: str) -> str:
    """
    @brief Чистит COMMENT ON TABLE от технического хвоста.
    @details
        В дампе: 'ОСВ: Номер счета, SysObjTypeEffective{id=..., ...}'.
        Оставляем смысловую часть до ', SysObjType'.
    """
    text = _unescape(raw)
    return re.split(r",\s*SysObjType", text)[0].strip()


def _clean_column_comment(raw: str) -> str:
    """
    @brief Чистит COMMENT ON COLUMN от технического хвоста.
    @details
        В дампе: 'Name, languageSchema=ru'. Оставляем 'Name'.
    """
    text = _unescape(raw)
    return re.split(r",\s*languageSchema", text)[0].strip()


def _parse_columns(body: str) -> list[Column]:
    """
    @brief Парсит тело CREATE TABLE в список колонок.
    @details
        Каждая колонка на отдельной строке: "    name type modifiers,".
        Constraints в дампе вынесены в ALTER TABLE, поэтому в теле —
        только колонки.
    @param body  Содержимое скобок CREATE TABLE.
    @return      Список Column (пока без комментариев — их добавим позже).
    """
    columns: list[Column] = []
    for line in body.split("\n"):
        line = line.strip().rstrip(",").strip()
        if not line:
            continue
        parts = line.split(None, 1)  # имя + остальное (тип)
        if len(parts) != 2:
            continue
        name, col_type = parts
        name = name.strip('"')
        columns.append(Column(name=name, type=col_type.strip()))
    return columns


def parse_ddl(text: str) -> SchemaCatalog:
    """
    @brief Главная функция: текст дампа → SchemaCatalog.
    @param text  Полное содержимое data_model.sql.
    @return      SchemaCatalog со всеми таблицами, PK, FK, комментариями.
    """
    tables: dict[str, Table] = {}

    # 1. CREATE TABLE → таблицы и колонки
    for m in _RE_CREATE.finditer(text):
        name, body = m.group(1), m.group(2)
        tables[name] = Table(name=name, columns=_parse_columns(body))

    # 2. PRIMARY KEY
    for m in _RE_PK.finditer(text):
        name, cols = m.group(1), m.group(2)
        if name in tables:
            tables[name].primary_key = [c.strip() for c in cols.split(",")]

    # 3. FOREIGN KEY (включая закомментированные)
    for m in _RE_FK.finditer(text):
        name, col, ref_table, ref_col = m.groups()
        if name in tables:
            tables[name].foreign_keys.append(
                ForeignKey(
                    column=col.strip(),
                    ref_table=ref_table.strip(),
                    ref_column=ref_col.strip(),
                )
            )

    # 4. COMMENT ON TABLE
    for m in _RE_COMMENT_TABLE.finditer(text):
        name, raw = m.group(1), m.group(2)
        if name in tables:
            tables[name].comment = _clean_table_comment(raw)

    # 5. COMMENT ON COLUMN
    col_comments: dict[tuple[str, str], str] = {}
    for m in _RE_COMMENT_COLUMN.finditer(text):
        tname, cname, raw = m.group(1), m.group(2), m.group(3)
        col_comments[(tname, cname)] = _clean_column_comment(raw)
    for table in tables.values():
        for col in table.columns:
            comm = col_comments.get((table.name, col.name))
            if comm:
                col.comment = comm

    return SchemaCatalog(tables=list(tables.values()))


def parse_file(path: str) -> SchemaCatalog:
    """@brief Читает файл и парсит. @param path Путь к data_model.sql."""
    with open(path, "r", encoding="utf-8") as f:
        return parse_ddl(f.read())
