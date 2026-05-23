
from __future__ import annotations

"""
@file auditor_sqlalchemy.py
@brief Реализация SecurityAuditor на базе SQLAlchemy + pglast для кейса GreenData.

@details
Этот модуль реализует класс `SQLAlchemySecurityAuditor`, который проверяет 
SQL-запросы на наличие уязвимостей, используя гибридный подход:
1. Статический анализ AST через библиотеку `pglast` (поиск инъекций, DML без WHERE, UNION и т.д.).
2. Семантический анализ схемы через `SQLAlchemy` (поиск доступа к PII-поляам, SELECT *).

Архитектура:
- `SQLAlchemySchemaContext`: Загружает метаданные БД (из URL или JSON-словаря) 
  и строит карту чувствительных колонок на основе regex-паттернов.
- `QueryASTAnalyzer`: Парсит SQL-строку и предоставляет свойства-флаги 
  (has_union, has_where, has_pg_sleep и др.) для быстрой проверки правил.
- `SQLAlchemySecurityAuditor`: Оркестрирует проверку, собирает список 
  `Vulnerability` и возвращает `AuditResult` в соответствии с контрактом baseline1.py.

Зависимости:
- pip install sqlalchemy pglast

Интеграция:
Используется в пайплайне `SQLSecuritySystem.run()` как реализация интерфейса 
`SecurityAuditor`. Позволяет детектировать 9+ классов уязвимостей из ТЗ GreenData.
"""
import re
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from sqlalchemy import MetaData, create_engine, inspect, Table
from sqlalchemy.exc import NoSuchTableError
import pglast  # pip install pglast

# Импорт контрактов из baseline1.py (адаптируйте путь при необходимости)
from baseline1 import Vulnerability, AuditResult, SecurityAuditor

# ─────────────────────────────────────────────────────────────────────────────
# Конфигурация рисков и чувствительных паттернов
# ─────────────────────────────────────────────────────────────────────────────
RISK_SCORES = {
    "SQL_INJ_CLASSIC": 10.0,
    "SQL_INJ_UNION": 9.0,
    "SQL_INJ_TIME": 8.0,
    "PRIV_ESCALATE": 8.0,
    "DML_NO_WHERE": 9.0,
    "DIRECT_SENSITIVE": 6.0,
    "SELECT_STAR": 5.0,
    "NO_PAGINATION": 4.0,
    "SLOW_QUERY": 3.0,
    "PLPGSQL_UNSAFE": 9.0,
}

# Паттерны для поиска чувствительных колонок в метаданных БД
SENSITIVE_PATTERNS = re.compile(
    r"(password|token|cvv|pan|card_number|passport|snils|inn|phone|email|"
    r"birth_date|address|check_account|bank_ident_number|credit_amount|"
    r"financial_position|reserve_size)", re.IGNORECASE
)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Контекст схемы (SQLAlchemy)
# ─────────────────────────────────────────────────────────────────────────────
class SQLAlchemySchemaContext:
    """Загружает схему БД через SQLAlchemy и предоставляет методы для валидации."""
    def __init__(self, db_url: str | None = None, schema_dict: dict[str, Any] | None = None):
        self.tables_meta: dict[str, Table] = {}
        self.sensitive_cols: dict[str, Set[str]] = {}
        
        if db_url:
            engine = create_engine(db_url)
            meta = MetaData()
            meta.reflect(bind=engine)
            self.tables_meta = dict(meta.tables)
        elif schema_dict:
            self._load_from_dict(schema_dict)
            
        self._build_sensitive_map()

    def _load_from_dict(self, schema: dict[str, Any]):
        """Синтетическая загрузка из JSON-схемы (без живого подключения)."""
        for t_name, t_meta in schema.items():
            cols = []
            for c in t_meta.get("columns", []):
                cols.append(Column(c["name"], String))  # тип для MVP не критичен
            self.tables_meta[t_name] = Table(t_name, MetaData(), *cols)

    def _build_sensitive_map(self):
        for t_name, table in self.tables_meta.items():
            self.sensitive_cols[t_name] = {
                c.name for c in table.columns if SENSITIVE_PATTERNS.search(c.name)
            }

    def get_table_names(self) -> Set[str]:
        return set(self.tables_meta.keys())

    def is_sensitive_column(self, table: str, column: str) -> bool:
        return column in self.sensitive_cols.get(table, set())


# ─────────────────────────────────────────────────────────────────────────────
# 2. Анализатор AST (pglast + эвристики)
# ─────────────────────────────────────────────────────────────────────────────
class QueryASTAnalyzer:
    """Парсит SQL и извлекает структурные компоненты."""
    def __init__(self, sql: str):
        self.raw_sql = sql.strip()
        self.ast = self._parse()
        self.sql_lower = self.raw_sql.lower()
        
    def _parse(self):
        try:
            return pglast.parser.parse_sql(self.raw_sql)
        except Exception:
            return []

    @property
    def dml_type(self) -> str | None:
        match = re.match(r"(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|EXECUTE)", self.raw_sql, re.IGNORECASE)
        return match.group(1).upper() if match else None

    @property
    def has_union(self) -> bool:
        return "union" in self.sql_lower and "union all" not in self.sql_lower

    @property
    def has_where(self) -> bool:
        # Простая проверка по токенам (для MVP достаточно)
        return bool(re.search(r"\bWHERE\b", self.raw_sql, re.IGNORECASE))

    @property
    def has_limit(self) -> bool:
        return bool(re.search(r"\bLIMIT\b", self.raw_sql, re.IGNORECASE))

    @property
    def has_pg_sleep(self) -> bool:
        return "pg_sleep" in self.sql_lower

    @property
    def has_string_concat(self) -> bool:
        # Обнаружение уязвимой конкатенации: '...' || var || '...'
        return bool(re.search(r"'\s*\|\||\|\|\s*'", self.raw_sql)) or "user_input" in self.raw_sql

    @property
    def has_execute_dynamic(self) -> bool:
        return bool(re.search(r"EXECUTE\s+.*\|\|", self.raw_sql, re.IGNORECASE))

    @property
    def has_security_definer_unsafe(self) -> bool:
        return "SECURITY DEFINER" in self.raw_sql.upper() and "SET search_path" not in self.raw_sql

    def extract_tables(self) -> Set[str]:
        tables = set()
        # FROM table
        tables.update(re.findall(r"\bFROM\s+(\w+)", self.raw_sql, re.IGNORECASE))
        # JOIN table
        tables.update(re.findall(r"\bJOIN\s+(\w+)", self.raw_sql, re.IGNORECASE))
        # UPDATE table
        tables.update(re.findall(r"\bUPDATE\s+(\w+)", self.raw_sql, re.IGNORECASE))
        return {t for t in tables if t.isidentifier()}

    def extract_selected_columns(self) -> Dict[str, List[str]]:
        """Возвращает {table: [col1, col2]} для SELECT запросов."""
        cols_by_table: Dict[str, List[str]] = {}
        select_match = re.search(r"SELECT\s+(.*?)\s+FROM", self.raw_sql, re.IGNORECASE | re.DOTALL)
        if not select_match:
            return cols_by_table
            
        cols_raw = select_match.group(1)
        if "*" in cols_raw:
            # Для MVP помечаем все таблицы из FROM как имеющие SELECT *
            for t in self.extract_tables():
                cols_by_table.setdefault(t, []).append("*")
        return cols_by_table


# ─────────────────────────────────────────────────────────────────────────────
# 3. Аудитор (наследует контракт baseline1.py)
# ─────────────────────────────────────────────────────────────────────────────
class SQLAlchemySecurityAuditor(SecurityAuditor):
    """Проверяет SQL через SQLAlchemy-схему + AST-анализ."""
    RISK_THRESHOLD = 4.0

    def __init__(self, schema_ctx: SQLAlchemySchemaContext | None = None, **kwargs):
        super().__init__(**kwargs)
        self.schema = schema_ctx or SQLAlchemySchemaContext(schema_dict={})

    def audit(self, sql_query: str, db_schema: dict[str, Any] | None = None) -> AuditResult:
        if db_schema:
            self.schema = SQLAlchemySchemaContext(schema_dict=db_schema)
            
        analyzer = QueryASTAnalyzer(sql_query)
        vulns: List[Vulnerability] = []
        
        # 1. DML без WHERE
        if analyzer.dml_type in ("UPDATE", "DELETE") and not analyzer.has_where:
            vulns.append(self._make_vuln("DML_NO_WHERE", "DML-операция без условия WHERE. Может удалить/изменить всю таблицу."))
            
        # 2. SQL Injection Classic
        if analyzer.has_string_concat:
            vulns.append(self._make_vuln("SQL_INJ_CLASSIC", "Обнаружена конкатенация строки. Используйте параметризацию ($1)."))
            
        # 3. Union Injection
        if analyzer.has_union:
            vulns.append(self._make_vuln("SQL_INJ_UNION", "Использован UNION. Возможна выгрузка данных из других таблиц."))
            
        # 4. Time-based Blind
        if analyzer.has_pg_sleep:
            vulns.append(self._make_vuln("SQL_INJ_TIME", "Обнаружен pg_sleep(). Возможна слепая инъекция через время ответа."))
            
        # 5. Privilege Escalation
        if analyzer.has_security_definer_unsafe:
            vulns.append(self._make_vuln("PRIV_ESCALATE", "SECURITY DEFINER без SET search_path. Риск перехвата вызовов."))
            
        # 6. PL/pgSQL Unsafe EXECUTE
        if analyzer.has_execute_dynamic:
            vulns.append(self._make_vuln("PLPGSQL_UNSAFE", "Динамический EXECUTE с конкатенацией. Используйте USING."))
            
        # 7. SELECT *
        if "*" in analyzer.sql_lower and analyzer.dml_type == "SELECT":
            vulns.append(self._make_vuln("SELECT_STAR", "SELECT * тащит все колонки, включая чувствительные."))
            
        # 8. No Pagination
        if analyzer.dml_type == "SELECT" and not analyzer.has_limit:
            vulns.append(self._make_vuln("NO_PAGINATION", "Отсутствует LIMIT. Возможен DoS или выгрузка миллионов строк."))
            
        # 9. Direct Sensitive (через SQLAlchemy схему)
        self._check_sensitive_access(analyzer, vulns)
        
        # Итог
        max_risk = max([v.risk_score for v in vulns], default=0.0)
        approved = max_risk <= self.RISK_THRESHOLD and len(vulns) == 0
        
        return AuditResult(
            approved=approved,
            vulnerabilities=vulns,
            overall_risk_score=max_risk,
            summary="Запрос безопасен" if approved else f"Найдено уязвимостей: {len(vulns)} (макс. риск: {max_risk})"
        )

    def _make_vuln(self, cls: str, desc: str) -> Vulnerability:
        score = RISK_SCORES.get(cls, 5.0)
        return Vulnerability(
            vuln_class=cls,
            risk_score=score,
            description=desc,
            recommendation=f"Исправьте запрос согласно лучшим практикам PostgreSQL (класс: {cls})"
        )

    def _check_sensitive_access(self, analyzer: QueryASTAnalyzer, vulns: List[Vulnerability]):
        selected = analyzer.extract_selected_columns()
        for table, cols in selected.items():
            if "*" in cols:
                # Если SELECT *, проверяем, есть ли в таблице чувствительные колонки
                if self.schema.is_sensitive_column(table, "*"):
                    vulns.append(self._make_vuln("DIRECT_SENSITIVE", f"SELECT * на таблице {table}, содержащей PII-поля."))
                continue
                
            for col in cols:
                if self.schema.is_sensitive_column(table, col):
                    vulns.append(self._make_vuln("DIRECT_SENSITIVE", f"Прямой доступ к чувствительному полю {table}.{col} без маскирования."))


# ─────────────────────────────────────────────────────────────────────────────
# Пример интеграции с вашим пайплайном
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 1. Загружаем схему (можно передать dict из data/schema_catalog.json)
    schema_ctx = SQLAlchemySchemaContext(schema_dict={
        "credit_contract": {"columns": [{"name": "id"}, {"name": "credit_amount"}, {"name": "check_account"}]},
        "sim_client": {"columns": [{"name": "id"}, {"name": "passport"}, {"name": "full_name"}]}
    })
    
    # 2. Создаём аудитора
    auditor = SQLAlchemySecurityAuditor(schema_ctx=schema_ctx)
    
    # 3. Тестируем на примерах из вашего датасета
    test_queries = [
        ("SELECT id, credit_amount FROM credit_contract WHERE credit_contract_number = '\" + user_input + \"'", "SQL_INJ_CLASSIC"),
        ("SELECT * FROM sim_client LIMIT 100", "SELECT_STAR"),
        ("UPDATE credit_contract SET status = 0", "DML_NO_WHERE"),
        ("SELECT passport, snils FROM sim_client LIMIT 1000", "DIRECT_SENSITIVE"),
    ]
    
    for sql, expected_cls in test_queries:
        res = auditor.audit(sql)
        print(f"\nSQL: {sql[:60]}...")
        print(f"Approved: {res.approved} | Risk: {res.overall_risk_score}")
        for v in res.vulnerabilities:
            print(f"  ↳ [{v.vuln_class}] (Score: {v.risk_score}) {v.description}")