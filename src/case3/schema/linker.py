"""
@file linker.py
@brief Schema linking — выбор релевантных таблиц из 60 под NL-задачу (ADR-0003).

@details
    «Узкое место» на 60 таблицах: всю схему в промпт не вложить. Линкер
    отбирает top-K релевантных таблиц + FK-замыкание (чтобы JOIN были валидны)
    и отдаёт компактный кусок схемы для промпта генератора.

    MVP — лексический матчинг по русским COMMENT (в каталоге богатые описания
    таблиц и колонок). Без новых зависимостей. Апгрейд — эмбеддинги
    (e5-multilingual + FAISS), контракт link_text/link_dict тот же.

    Источник схемы: data/schema_catalog.json
        {"tables": [{"name","comment","columns":[{name,type,comment}],
                     "primary_key":[...], "foreign_keys":[{column,ref_table,ref_column}]}]}
"""
from __future__ import annotations

import json
import os
import re

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_CATALOG = os.path.join(_ROOT, "data", "schema_catalog.json")

# стоп-слова (в prefix-5 форме) — глаголы-команды и предлоги, чтобы не шумели
_STOP = {"показ", "выгру", "дай", "ähн", "все", "всех", "по", "для", "из", "на",
         "спис", "вывед", "найди", "получ", "table", "колон", "запро"}
# boilerplate-колонки: дубли и аудит-поля, не несут смысла для NL→SQL
_NOISE_COLS = {"name__ru", "name__en", "afr_ident", "afr_ord", "afr_note",
               "created_emp_id", "last_modified_emp_id", "last_modified_user_id",
               "last_modified_date"}
# generic-комментарии (англ. boilerplate) — не выводим, экономим токены
_GENERIC_COMMENT = {"name", "id", "create date", ""}


def _short_type(t: str) -> str:
    """@brief Компактный тип для DDL: 'character varying(2000) NOT NULL' → 'varchar'."""
    t = (t or "").split(" NOT NULL")[0].split(" DEFAULT")[0].strip()
    return (t.replace("character varying", "varchar")
             .replace("timestamp without time zone", "timestamp")
             .replace("double precision", "float")
             .replace("integer", "int"))


def _tokens(s: str) -> set[str]:
    """@brief Токены (кириллица+латиница), prefix-5 как дешёвый стеммер для русского."""
    toks = {w[:5] for w in re.findall(r"[a-zа-яё0-9]{3,}", (s or "").lower())}
    return toks - _STOP


class SchemaLinker:
    """@brief Schema-linker: лексический (по умолч.) ИЛИ семантический (bge-m3, опц.).

    @details
        Семантический ранкер активируется, когда HF_TOKEN задан в env:
        bge-m3 даёт описание каждой таблицы (имя + comment + 6 значимых
        column-comments) в 1024-мерное пространство, ранжирование — cosine.
        Эмбеддинги таблиц считаются ЛЕНИВО и кэшируются на диск
        (data/embeddings_cache.json). После первого прогрева стоимость =
        1 HTTP-API на пользовательскую задачу.

        На лексически прозрачных задачах семантика не сильно лучше Jaccard'а.
        Преимущество — на абстрактных формулировках: «отчёт по рискам»
        лексически не сопоставится с `scp_application` (заявка), а
        семантически — да (риск ~ скоринг заявки).
    """

    def __init__(self, catalog_path: str = _CATALOG):
        cat = json.load(open(catalog_path, encoding="utf-8"))["tables"]
        self.tables: dict[str, dict] = {}
        for t in cat:
            head = f"{t['name']} {t.get('comment') or ''}"
            body = " ".join(f"{c['name']} {c.get('comment') or ''}" for c in t["columns"])
            # Текст для эмбеддинга: имя + comment + первые 6 значимых column-comments.
            # Без всех 100+ колонок (для широких таблиц)— иначе вектор размывается.
            col_comments = [c.get("comment") or "" for c in t["columns"]
                            if (c.get("comment") or "").strip()
                            and (c.get("comment") or "").lower() not in {"name", "id", "create date"}]
            sem_text = f"{t['name']}. {t.get('comment') or ''}. " + " ".join(col_comments[:6])
            self.tables[t["name"]] = {
                "comment": t.get("comment") or "",
                "columns": t["columns"],
                "fks": t.get("foreign_keys") or [],
                "head_tok": _tokens(head),
                "all_tok": _tokens(head + " " + body),
                "sem_text": sem_text.strip(),
                "sem_vec": None,                    # ленивая инициализация (см. _ensure_semantic)
            }
        # embeddings-клиент: singleton. Если HF_TOKEN нет — available()==False, fallback лексика.
        try:
            from case3.llm.embeddings import get_embeddings_client
            self._ec = get_embeddings_client()
        except Exception:
            self._ec = None
        self._sem_ready = False

    def _ensure_semantic(self) -> bool:
        """@brief Прогреть эмбеддинги для всех 60 таблиц одним батчем. Idempotent.
        Возвращает False, если HF_TOKEN не задан или эмбеддинги не считаются."""
        if self._sem_ready:
            return True
        if not self._ec or not self._ec.available():
            return False
        texts = [self.tables[n]["sem_text"] for n in self.tables]
        vecs = self._ec.embed_batch(texts)
        if not any(v is not None for v in vecs):
            return False
        for n, v in zip(self.tables.keys(), vecs):
            self.tables[n]["sem_vec"] = v
        self._ec.save_cache()
        self._sem_ready = True
        return True

    def _score(self, qt: set[str], info: dict) -> int:
        return len(qt & info["all_tok"]) + 2 * len(qt & info["head_tok"])

    def rank(self, task: str, k: int = 6) -> list[tuple[str, float]]:
        """@brief top-K таблиц по релевантности (имя, score>0). Семантика → лексика."""
        if self._ensure_semantic():
            qv = self._ec.embed(task)
            if qv is not None:
                from case3.llm.embeddings import EmbeddingsClient
                scored: list[tuple[str, float]] = []
                for n, info in self.tables.items():
                    tv = info["sem_vec"]
                    if tv is None:
                        continue
                    s = EmbeddingsClient.cosine(qv, tv)
                    if s > 0:
                        scored.append((n, s))
                return sorted(scored, key=lambda x: -x[1])[:k]
        # Лексический fallback
        qt = _tokens(task)
        scored_lex = [(n, float(self._score(qt, i))) for n, i in self.tables.items()]
        return sorted([x for x in scored_lex if x[1] > 0], key=lambda x: -x[1])[:k]

    def link_dict(self, task: str, k: int = 6, fk_closure: bool = True) -> dict[str, list[str]]:
        """@brief {таблица: [колонки]} для top-K (+ FK-замыкание на 1 хоп)."""
        chosen = {n for n, _ in self.rank(task, k)}
        if fk_closure:
            for n in list(chosen):
                for fk in self.tables[n]["fks"]:
                    ref = fk.get("ref_table")
                    if ref in self.tables:
                        chosen.add(ref)
        return {n: [c["name"] for c in self.tables[n]["columns"]] for n in chosen}

    def link_text(self, task: str, k: int = 4, max_cols: int = 15,
                  fk_closure: bool = False) -> str:
        """@brief Схема для промпта в стиле DAIL-SQL Code-Representation (CREATE TABLE DDL).

        Компактно, С ТИПАМИ (модель не путает smallint с boolean), значимые
        комментарии инлайном, boilerplate-колонки выкинуты. Источник: DAIL-SQL
        (Code Representation — лучший способ подачи схемы), круг 2 ресёрча."""
        ranked = [n for n, _ in self.rank(task, k)]
        if fk_closure:
            for n in list(ranked):
                for fk in self.tables[n]["fks"]:
                    ref = fk.get("ref_table")
                    if ref in self.tables and ref not in ranked:
                        ranked.append(ref)
        blocks = []
        for n in ranked:
            info = self.tables[n]
            fks = {fk["column"]: (fk.get("ref_table"), fk.get("ref_column", "id"))
                   for fk in info["fks"]}                # карта FK для подсказок
            all_cols = [c for c in info["columns"] if c["name"] not in _NOISE_COLS]
            # Естественный порядок + FK-колонки гарантированно в DDL (дописываем в конец, если max_cols их обрезал)
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
                if com and com.lower() not in _GENERIC_COMMENT:
                    tail = f"  -- {com}{fk_hint}"
                elif fk_hint:
                    tail = f"  -- {fk_hint.lstrip()}"
                else:
                    tail = ""
                lines.append(f"  {c['name']} {_short_type(c['type'])},{tail}")
            head = f"CREATE TABLE {n} (" + (f"  -- {info['comment']}" if info["comment"] else "")
            blocks.append(head + "\n" + "\n".join(lines) + "\n);")
        return "\n\n".join(blocks)


def link_schema(task: str, k: int = 6) -> str:
    """@brief Удобная обёртка: текст схемы под задачу (для промпта генератора)."""
    return SchemaLinker().link_text(task, k=k)
