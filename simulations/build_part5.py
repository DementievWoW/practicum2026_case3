"""
@file build_part5.py
@brief Ноутбуки 13, 14, 15 — judge unreliability, latency budget, model size.
"""

from build_helpers import md, code, COMMON_PREAMBLE
from build_part4 import eng_footer


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 13 — LLM-as-judge ненадёжен → нужен гибрид
# ════════════════════════════════════════════════════════════════════════════
def build_13() -> list:
    cells = []

    cells.append(md("""\
        # 13 — LLM-as-judge ненадёжен → гибрид (правила + LLM)

        > **Проблема:** «спроси LLM есть ли SQLi» не работает надёжно.
        > **Решение (ADR-0004):** Phase 1 (детерминированные правила) выдаёт
        > findings → Phase 2 (LLM) делает **триаж** + объяснение с RAG-ссылками.

        ## Что покажем

        На 4 кейсах сравним:
        - **A.** Только Phase 1 (алгоритм) → видим FP и FN.
        - **B.** Только Phase 2 (LLM-only) → видим inconsistency.
        - **C.** Гибрид (Phase 1 → Phase 2 триаж) → FP отсеяны, объяснения с CWE.

        Все «вызовы LLM» — mock-функции.
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        Идёт спортивный турнир. Есть два судьи:
        - **Робот-судья** с правилами «если игрок упал → красная карточка».
          Точный, но **тупой**: упал по своей инициативе → красная.
          Не упал в очевидном фоле → ничего.
        - **Человек-судья** смотрит контекст: «упал, но симулировал → нет
          карточки. Не упал, но фол был → жёлтая». Гибче, но **устаёт**
          и иногда ошибается, забывает правила.

        **Гибрид:** робот размечает «формальные нарушения», человек
        делает финальное решение с учётом контекста. Это и есть Phase 1
        + Phase 2.
        """))

    cells.append(md("""\
        ## 1. Setup — 4 кейса
        """))

    cells.append(code(COMMON_PREAMBLE + """

##
# @brief 4 кейса для сравнения судей.
# @details
#   FP — false positive (алгоритм кричит, на самом деле всё ок).
#   FN — false negative (алгоритм молчит, реально уязвимо).
#   TP — true positive (всё корректно).
#   TN — true negative.
CASES = [
    {
        "id": "case-1-legitimate-pg-sleep",
        "sql": "-- миграция, пауза для autovacuum\\nALTER TABLE big SET (autovacuum_vacuum_scale_factor = 0.01);\\nSELECT pg_sleep(1);",
        "ground_truth_vuln": False,
        "context_note": "DDL-миграция, нет user input, pg_sleep ради autovacuum",
        "kind": "FP-test (тест на ложное срабатывание)",
    },
    {
        "id": "case-2-blind-injection",
        "sql": "UPDATE last_seen SET ts=now() WHERE user_id = 1 OR (CASE WHEN substr((SELECT password FROM users WHERE id=1),1,1)='a' THEN pg_sleep(2) ELSE 0 END)",
        "ground_truth_vuln": True,
        "context_note": "blind exfil через time-based CASE",
        "kind": "TP-test (надо поймать)",
    },
    {
        "id": "case-3-semantic-leak",
        "sql": "SELECT u.id, u.login, r.permissions FROM users u JOIN role_assignments ra ON ra.user_id=u.id JOIN roles r ON r.id=ra.role_id",
        "ground_truth_vuln": True,
        "context_note": "permissions = JSON прав доступа; имя колонки не матчит regex sensitive",
        "kind": "FN-test (формально ок, по смыслу — leak)",
    },
    {
        "id": "case-4-safe-aggregate",
        "sql": "SELECT COUNT(*) FROM clients WHERE balance > 100000",
        "ground_truth_vuln": False,
        "context_note": "агрегат, ничего не утекает",
        "kind": "TN-test (молчать)",
    },
]

for c in CASES:
    print(f"  [{c['kind']:35s}] {c['id']}")
"""))

    cells.append(md("""\
        ## 2. Judge A — только Phase 1 (детерминированный)
        """))

    cells.append(code("""\
##
# @brief Phase 1 — простой rule-based детектор.
def judge_A_rules_only(sql):
    findings = []
    if re.search(r"\\bpg_sleep\\s*\\(", sql, re.IGNORECASE):
        findings.append({"rule_id": "R006-pg-sleep", "vuln_class": "SQL_INJ_TIME", "risk": 8})
    if re.search(r"\\bDELETE\\b|\\bUPDATE\\b", sql, re.IGNORECASE) and \\
       not re.search(r"\\bWHERE\\b", sql, re.IGNORECASE):
        findings.append({"rule_id": "R002/R003", "vuln_class": "DML_NO_WHERE", "risk": 9})
    if re.search(r"SELECT\\s+\\*", sql, re.IGNORECASE):
        findings.append({"rule_id": "R001", "vuln_class": "SELECT_STAR", "risk": 5})
    # Прямой regex на имена sensitive — limited
    for col in re.findall(r"\\b(password|passport|card_number|ssn)\\b", sql, re.IGNORECASE):
        findings.append({"rule_id": "R009", "vuln_class": "DIRECT_SENSITIVE", "risk": 7})
    return findings


section("Judge A (только правила) — прогон")
for c in CASES:
    f = judge_A_rules_only(c["sql"])
    pred_vuln = bool(f)
    correct = pred_vuln == c["ground_truth_vuln"]
    mark = "✅" if correct else "❌"
    print(f"  {mark} {c['id']:35s}  pred={pred_vuln}  truth={c['ground_truth_vuln']}  findings={len(f)}")
"""))

    cells.append(md("""\
        ## 3. Judge B — только LLM (mock, имитирует inconsistency)
        """))

    cells.append(code("""\
import random as _rnd


##
# @brief Mock LLM-only judge — имитирует, что LLM «угадывает» по контексту,
#        но без structured findings часто ошибается.
def judge_B_llm_only(sql, seed=None):
    rng = _rnd.Random(seed)
    # Реальный LLM на голом SQL без RAG/findings даёт ~70% точности
    # с inconsistency между прогонами. Симулируем шум.
    sql_lo = sql.lower()
    score = 0.0
    if "pg_sleep" in sql_lo and "case" in sql_lo:
        score = 0.8
    elif "pg_sleep" in sql_lo:
        score = 0.5  # не различает blind vs миграцию
    elif "delete" in sql_lo and "where" not in sql_lo:
        score = 0.9
    elif "select *" in sql_lo:
        score = 0.4
    elif "permissions" in sql_lo:
        score = 0.3  # не понимает семантику JSON прав
    score += rng.uniform(-0.2, 0.2)  # inconsistency
    return score > 0.5


section("Judge B (только LLM) — 3 прогона на каждом кейсе (для inconsistency)")
for c in CASES:
    runs = [judge_B_llm_only(c["sql"], seed=i) for i in range(3)]
    consistent = len(set(runs)) == 1
    mark = "✅" if all(r == c["ground_truth_vuln"] for r in runs) else "❌"
    print(f"  {mark} {c['id']:35s}  прогоны={runs}  consistent={consistent}")
"""))

    cells.append(md("""\
        ## 4. Judge C — гибрид (Phase 1 → Phase 2 триаж + RAG)
        """))

    cells.append(code("""\
##
# @brief Mock RAG — словарь CWE/CAPEC-чанков.
RAG_KB = {
    "R001":      {"cwe_id": "CWE-1295", "doc": "SELECT * раскрывает все колонки, включая возможно чувствительные."},
    "R002/R003": {"cwe_id": "CWE-1284", "doc": "UPDATE/DELETE без WHERE затрагивает все строки таблицы."},
    "R006-pg-sleep": {"cwe_id": "CWE-89", "capec_id": "CAPEC-7", "doc": "pg_sleep в условии CASE — индикатор blind SQLi."},
    "R009":      {"cwe_id": "CWE-200", "doc": "Прямой доступ к ПДн без маскирования."},
}


##
# @brief Phase 2 — LLM-триаж findings с RAG. Mock через rule-based решения.
def phase2_triage(sql, findings, context_note=""):
    \"\"\"@brief Триажит каждый finding, отсеивает FP по контексту, добавляет evidence.\"\"\"
    triaged = []
    for f in findings:
        # FP-фильтр: если в SQL есть DDL/комментарий «миграция» и pg_sleep — отбрасываем
        if f["rule_id"] == "R006-pg-sleep":
            if "ALTER TABLE" in sql.upper() or "миграция" in sql.lower():
                continue  # FP — legitimate
            # CASE WHEN ... pg_sleep — это blind, повышаем risk
            if "CASE" in sql.upper() and "WHEN" in sql.upper():
                f["risk"] = 9
        # FP-фильтр для DML без WHERE: TRUNCATE-like → low
        if f["rule_id"] == "R002/R003" and re.search(r"--.*очист", sql, re.IGNORECASE):
            f["risk"] = 2
        rag = RAG_KB.get(f["rule_id"], {})
        f["evidence"] = rag
        triaged.append(f)

    # Phase 2 ищет дополнительные семантические уязвимости, которые Phase 1 пропустил
    # (mock: ищем JSON-permissions через имя)
    if "permissions" in sql.lower() and not any("R009" in t["rule_id"] for t in triaged):
        triaged.append({
            "rule_id":     "R009-semantic",
            "vuln_class":  "DIRECT_SENSITIVE",
            "risk":        7,
            "evidence":    {"cwe_id": "CWE-200", "doc": "permissions = JSON прав, утечка"},
            "_from":       "phase2-semantic",
        })
    return triaged


def judge_C_hybrid(sql, context_note=""):
    phase1 = judge_A_rules_only(sql)
    return phase2_triage(sql, phase1, context_note)


section("Judge C (гибрид) — прогон")
for c in CASES:
    f = judge_C_hybrid(c["sql"], c["context_note"])
    pred_vuln = bool(f)
    correct = pred_vuln == c["ground_truth_vuln"]
    mark = "✅" if correct else "❌"
    print(f"  {mark} {c['id']:35s}  pred={pred_vuln}  truth={c['ground_truth_vuln']}")
    for finding in f:
        evidence = finding.get("evidence", {})
        cwe = evidence.get("cwe_id", "—")
        print(f"        - {finding['rule_id']:15s} risk={finding['risk']}  CWE={cwe}")
"""))

    cells.append(md("""\
        ## 5. Сравнение Precision / Recall
        """))

    cells.append(code("""\
def metrics(judge_fn, name):
    tp = fp = tn = fn = 0
    for c in CASES:
        try:
            pred = bool(judge_fn(c["sql"], c.get("context_note", "")))
        except TypeError:
            pred = bool(judge_fn(c["sql"]))
        truth = c["ground_truth_vuln"]
        if pred and truth:    tp += 1
        elif pred and not truth: fp += 1
        elif not pred and truth: fn += 1
        else: tn += 1
    p = tp / (tp + fp) if (tp + fp) else 0
    r = tp / (tp + fn) if (tp + fn) else 0
    return name, p, r, {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


section("Финальное сравнение")
print(f"{'судья':<22} {'precision':>10} {'recall':>10}   counts")
print("-" * 72)
for fn, label in [(judge_A_rules_only, "A — правила"),
                  (judge_B_llm_only,   "B — LLM-only"),
                  (judge_C_hybrid,     "C — гибрид")]:
    n, p, r, c = metrics(fn, label)
    print(f"{n:<22} {p:>10.2f} {r:>10.2f}   {c}")
"""))

    cells.append(eng_footer("04-llm-judge-unreliability"))
    return cells


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 14 — Бюджет латентности 40 секунд
# ════════════════════════════════════════════════════════════════════════════
def build_14() -> list:
    cells = []

    cells.append(md("""\
        # 14 — Бюджет латентности 40 секунд

        > **Мягкое ограничение** от ментора: live-demo не должно «зависать»
        > больше 40 секунд на один прогон цикла.
        >
        > **Решение (ADR-0008/ADR-0009):** budget cap в state + graceful
        > degradation, если превышен — finalize с лучшим имеющимся SQL.

        ## Что покажем

        1. Симулируем времена узлов через `time.sleep` (масштаб ×100 уменьшен
           чтобы ноутбук не тормозил: «5 сек» → 50 мс).
        2. LoopState с tracker'ом времени и токенов.
        3. **Sample run** (2 итерации) → укладываемся.
        4. **Stress run** (5 итераций) → превышаем → degraded result.
        5. Гистограмма p50/p95/p99 на 100 синтетических прогонах.
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        Ты копишь карманные деньги — у тебя есть **40 рублей в день**.
        Хочешь купить мороженое (10₽), пирожок (15₽), сок (10₽), жвачку (10₽).
        В сумме — 45₽, не хватает.

        - **Без бюджета:** покупаешь всё подряд, не считая. К концу дня
          узнаёшь что вышел в минус — у мамы выпрашиваешь.
        - **С бюджетом:** считаешь по ходу. Купил мороженое+пирожок+сок=35₽.
          Подходишь к жвачке — видишь, остаётся 5₽ — отказываешься от неё.
          Это **graceful degradation**: жвачку не получил, но и в минус не ушёл.

        В нашем цикле «время» = «бюджет». Если итерация 3 уже потратила 30 сек —
        можно ли запускать reflector + iter 4? Считаем.
        """))

    cells.append(md("""\
        ## 1. Симуляция времён узлов
        """))

    cells.append(code(COMMON_PREAMBLE + """

##
# @brief Времена узлов цикла (масштабировано ×100: «5 сек» → 50 мс).
# @details
#   В Colab эти задержки реальны — ноутбук будет действительно ждать.
#   Используем небольшие числа, чтобы общее время прогона ноутбука < 30 сек.
SCALE = 0.01  # «секунды» → миллисекунды

NODE_DURATIONS = {
    "schema_link":      0.5,
    "generator":        7.0,
    "auditor_phase1":   1.0,
    "auditor_phase2":   4.0,
    "reflector":        2.0,
    "finalize":         0.3,
}


##
# @brief Сценарий одного запуска: список узлов в порядке.
def make_pipeline(n_iterations):
    p = ["schema_link"]
    for _ in range(n_iterations):
        p += ["generator", "auditor_phase1", "auditor_phase2"]
    # Если итераций > 1, между ними был reflector (max_iter - 1 раз)
    if n_iterations > 1:
        # вставляем reflector между парами (упрощённо — не точные позиции)
        pass
    p.append("finalize")
    return p


print("Узлы и их «сек»:")
for n, d in NODE_DURATIONS.items():
    print(f"  {n:18s}  {d:>5.1f} sec")
print(f"\\nМасштаб времени в симуляции: SCALE = {SCALE} (1 «сек» = {SCALE*1000:.0f} ms)")
"""))

    cells.append(md("""\
        ## 2. State с budget cap
        """))

    cells.append(code("""\
from dataclasses import dataclass


@dataclass
class BudgetState:
    iteration: int = 0
    total_seconds: float = 0.0       # «секунды» (виртуальные)
    total_tokens: int = 0
    budget_seconds: float = 45.0
    budget_tokens: int = 80_000
    budget_exhausted: bool = False
    final_sql: str = ""

    def add(self, node, sec, tokens):
        self.total_seconds += sec
        self.total_tokens += tokens
        if self.total_seconds > self.budget_seconds or self.total_tokens > self.budget_tokens:
            self.budget_exhausted = True


def run_one_iter(state, with_reflector):
    \"\"\"@brief Прогон одной итерации цикла.\"\"\"
    state.iteration += 1
    if with_reflector:
        time.sleep(NODE_DURATIONS["reflector"] * SCALE)
        state.add("reflector", NODE_DURATIONS["reflector"], 200)
        if state.budget_exhausted: return
    for node in ("generator", "auditor_phase1", "auditor_phase2"):
        time.sleep(NODE_DURATIONS[node] * SCALE)
        # Имитация: generator/auditor тратят токены
        tokens = {"generator": 5000, "auditor_phase1": 0, "auditor_phase2": 3000}[node]
        state.add(node, NODE_DURATIONS[node], tokens)
        if state.budget_exhausted:
            return


def simulate_loop(n_iter_required):
    \"\"\"@brief Полный прогон цикла.\"\"\"
    state = BudgetState()
    time.sleep(NODE_DURATIONS["schema_link"] * SCALE)
    state.add("schema_link", NODE_DURATIONS["schema_link"], 0)
    for i in range(n_iter_required):
        run_one_iter(state, with_reflector=(i > 0))
        if state.budget_exhausted:
            state.final_sql = "SQL_from_last_valid_iter (graceful)"
            return state
    time.sleep(NODE_DURATIONS["finalize"] * SCALE)
    state.add("finalize", NODE_DURATIONS["finalize"], 0)
    state.final_sql = "SQL_approved"
    return state
"""))

    cells.append(md("""\
        ## 3. Sample run — 2 итерации укладываются в бюджет
        """))

    cells.append(code("""\
section("Sample run: 2 итерации (типичный случай)")
import time as _t
t0 = _t.time()
s = simulate_loop(2)
real_elapsed = _t.time() - t0

print(f"  iterations:        {s.iteration}")
print(f"  итого «секунд»:    {s.total_seconds:.1f} / {s.budget_seconds}")
print(f"  итого «токенов»:   {s.total_tokens} / {s.budget_tokens}")
print(f"  budget_exhausted:  {s.budget_exhausted}")
print(f"  final_sql:         {s.final_sql}")
print(f"  (реально в Colab прошло: {real_elapsed*1000:.0f} ms)")
"""))

    cells.append(md("""\
        ## 4. Stress run — 5 итераций, бюджет лопается
        """))

    cells.append(code("""\
section("Stress run: 5 итераций (worst case)")
t0 = _t.time()
s = simulate_loop(5)
real_elapsed = _t.time() - t0

print(f"  iterations:        {s.iteration}")
print(f"  итого «секунд»:    {s.total_seconds:.1f} / {s.budget_seconds}")
print(f"  budget_exhausted:  {s.budget_exhausted}")
print(f"  final_sql:         {s.final_sql}  ← graceful degradation")
print(f"  (реально в Colab прошло: {real_elapsed*1000:.0f} ms)")
"""))

    cells.append(md("""\
        ## 5. Распределение латентности по 100 прогонам
        """))

    cells.append(code("""\
import random


def simulate_with_jitter():
    \"\"\"@brief Прогон с реальным распределением: 80% — 2 итер, 15% — 3, 5% — 5.\"\"\"
    rng = random.random()
    if rng < 0.80:
        n = 2
    elif rng < 0.95:
        n = 3
    else:
        n = 5
    # Делаем без time.sleep — только считаем
    state = BudgetState()
    state.add("schema_link", NODE_DURATIONS["schema_link"], 0)
    for i in range(n):
        if i > 0:
            state.add("reflector", NODE_DURATIONS["reflector"] + random.uniform(-0.5, 0.5), 200)
            if state.budget_exhausted: break
        for node in ("generator", "auditor_phase1", "auditor_phase2"):
            d = NODE_DURATIONS[node] * random.uniform(0.8, 1.2)
            state.add(node, d, 3000)
            if state.budget_exhausted: break
        if state.budget_exhausted: break
    if not state.budget_exhausted:
        state.add("finalize", NODE_DURATIONS["finalize"], 0)
    return state


latencies = []
exhausted = 0
for _ in range(100):
    s = simulate_with_jitter()
    latencies.append(s.total_seconds)
    if s.budget_exhausted:
        exhausted += 1

latencies.sort()
p50 = latencies[50]
p95 = latencies[95]
p99 = latencies[99]

section("Распределение латентности (100 прогонов)")
print(f"  p50 (median):           {p50:>5.1f} sec")
print(f"  p95:                    {p95:>5.1f} sec")
print(f"  p99:                    {p99:>5.1f} sec")
print(f"  превысили бюджет:       {exhausted}/100  ({exhausted}%)")
print()
print("  Цель ADR-0008 §5:")
print("    p50 ≤ 25 sec  →  выполнено" if p50 <= 25 else "    p50 ≤ 25 sec  →  ❌")
print(f"    p95 ≤ 40 sec  →  {'выполнено' if p95 <= 40 else '❌'}")
print(f"    exhausted ≤ 5%  →  {'выполнено' if exhausted <= 5 else '❌'}")

# Простая ASCII-гистограмма
section("ASCII-гистограмма (по 5-сек бакетам)")
buckets = {}
for l in latencies:
    b = int(l // 5) * 5
    buckets[b] = buckets.get(b, 0) + 1
for b in sorted(buckets):
    bar = "█" * buckets[b]
    print(f"  {b:>3}-{b+5:<3} sec  {bar} ({buckets[b]})")
"""))

    cells.append(eng_footer("05-latency-budget"))
    return cells


# ════════════════════════════════════════════════════════════════════════════
# Ноутбук 15 — Целевая модель ≤ 30B параметров
# ════════════════════════════════════════════════════════════════════════════
def build_15() -> list:
    cells = []

    cells.append(md("""\
        # 15 — Целевая модель ≤ 30B (Qwen-Coder vs облако)

        > **Требование заказчика:** «модели до 30 миллиардов параметров,
        > заказчик разворачивает в своём контуре с ограниченными ресурсами».
        >
        > **Решение (ADR-0008):** Qwen-Coder 32B primary, fallback на gpt-4o-mini,
        > OpenAI-совместимый контракт LLMClient — переключение моделей одной
        > строкой конфига.

        ## Что покажем

        1. `LLMClient` абстракция — один контракт для всех моделей.
        2. Mock-моделей: small (быстро, посредственно), medium, large (медленно, лучше).
        3. Тот же task через 3 модели — видим trade-off.
        4. Cost-калькулятор: цена прогона eval-set через каждую.
        5. **Где LLM реально нужен** — кратко по проекту (5 точек).
        """))

    cells.append(md("""\
        ## 🧒 Аналогия для ребёнка

        У тебя в гараже три инструмента:
        - **Маленькая отвёртка** — лёгкая, всегда с собой, но шуруп
          из бетонной стены не вытащит.
        - **Средний шуруповёрт** — справляется с большинством, неудобно
          таскать каждый день.
        - **Огромный перфоратор** — пробивает любую стену, но дома хранить
          негде, нужен прокат за 1000 ₽/день.

        В LLM то же: маленькая (7B) для простых, средняя (32B) для
        большинства, огромная (>100B) — когда нужна гарантия. Контракт
        `LLMClient` — это **универсальный держатель**, в который можно
        вставить любую: меняешь насадку, не меняешь руку.
        """))

    cells.append(md("""\
        ## 1. LLMClient контракт
        """))

    cells.append(code(COMMON_PREAMBLE + """

from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMConfig:
    \"\"\"@brief Универсальная конфигурация для любого OpenAI-compat провайдера.\"\"\"
    model: str
    base_url: str = "https://api.openai.com/v1"
    api_key: str = "mock"
    temperature: float = 0.2
    max_tokens: int = 2048
    timeout_s: float = 30.0
    # «характеристики» (для mock)
    quality: float = 0.7        # 0..1
    latency_per_1k_tokens: float = 1.0  # «сек»/1k токенов
    cost_per_1m_tokens: float = 1.0     # $/1M


class LLMClient:
    \"\"\"@brief Mock-клиент. В проде — httpx.post к /v1/chat/completions.\"\"\"

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    ##
    # @brief Mock chat-completion.
    # @return  dict с полями text, tokens_in, tokens_out, latency_seconds, cost_usd.
    def chat(self, messages, sql_to_generate=None):
        # Имитируем — генерируем SQL разного качества
        tokens_in = sum(len(m.get("content", "")) for m in messages) // 4
        tokens_out = 200 if not sql_to_generate else len(sql_to_generate) // 4
        latency = (tokens_in + tokens_out) / 1000 * self.cfg.latency_per_1k_tokens
        cost = (tokens_in + tokens_out) / 1_000_000 * self.cfg.cost_per_1m_tokens
        # Mock-вывод
        if self.cfg.quality > 0.85:
            sql = "SELECT id, full_name FROM clients WHERE balance > 0 LIMIT 100"
        elif self.cfg.quality > 0.6:
            sql = "SELECT * FROM clients WHERE balance > 0 LIMIT 100"  # с одним багом (SELECT *)
        else:
            sql = "SELECT * FROM clients"  # совсем плохо
        return {
            "text": sql,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_seconds": latency,
            "cost_usd": cost,
        }


# Три «модели» — mock-конфиги
SMALL = LLMConfig(model="qwen2.5-7b-instruct",
                  quality=0.55,
                  latency_per_1k_tokens=0.3,
                  cost_per_1m_tokens=0.18)
MEDIUM = LLMConfig(model="qwen2.5-coder-32b-instruct",
                   quality=0.78,
                   latency_per_1k_tokens=0.8,
                   cost_per_1m_tokens=0.66)
LARGE = LLMConfig(model="gpt-4o-mini",
                  quality=0.88,
                  latency_per_1k_tokens=0.5,
                  cost_per_1m_tokens=0.75)
"""))

    cells.append(md("""\
        ## 2. Один task через 3 модели
        """))

    cells.append(code("""\
task_messages = [
    {"role": "system", "content": "Ты — генератор PostgreSQL по NL-вопросам аналитиков. Возвращай только SQL."},
    {"role": "user",   "content": "покажи клиентов с положительным балансом, топ-100 по убыванию"},
]


def run_through(cfg, label):
    client = LLMClient(cfg)
    resp = client.chat(task_messages)
    print(f"  [{label:18s}]")
    print(f"    model:   {cfg.model}")
    print(f"    SQL:     {resp['text']}")
    print(f"    quality: ~{cfg.quality*100:.0f}%")
    print(f"    latency: {resp['latency_seconds']*1000:.0f} ms")
    print(f"    cost:    ${resp['cost_usd']:.6f}")
    print()


section("Один task через 3 модели")
run_through(SMALL,  "small (7B)")
run_through(MEDIUM, "medium (32B Qwen)")
run_through(LARGE,  "large (gpt-4o-mini)")
"""))

    cells.append(md("""\
        ## 3. Cost-калькулятор на полный eval-set
        """))

    cells.append(code("""\
def estimate_eval_cost(cfg, n_questions=120, avg_in_tokens=15000, avg_out_tokens=400, iters_per_q=2.0):
    \"\"\"@brief Оценка стоимости прогона eval-set ADR-0006.\"\"\"
    per_q_tokens = (avg_in_tokens + avg_out_tokens) * iters_per_q
    total_tokens = per_q_tokens * n_questions
    cost = total_tokens / 1_000_000 * cfg.cost_per_1m_tokens
    latency_total = total_tokens / 1000 * cfg.latency_per_1k_tokens
    return cost, latency_total


section("Полный прогон eval-set (120 вопросов × 2 итерации)")
print(f"{'модель':<28} {'cost $':>10} {'wall time (мин)':>18}")
print("-" * 60)
for cfg, label in [(SMALL, "small (7B)"),
                   (MEDIUM, "medium (32B Qwen)"),
                   (LARGE, "large (gpt-4o-mini)")]:
    c, t = estimate_eval_cost(cfg)
    print(f"{cfg.model:<28} {c:>10.2f} {t/60:>18.1f}")
"""))

    cells.append(md("""\
        ## 4. Переключение моделей одной строкой
        """))

    cells.append(code("""\
section("Переключение через DI — один и тот же код работает с любой моделью")

# В реальном проекте generator-узел LangGraph получает LLMClient через DI
class GeneratorNode:
    def __init__(self, client: LLMClient):
        self.client = client

    def __call__(self, task):
        return self.client.chat([
            {"role": "system", "content": "PG SQL generator"},
            {"role": "user",   "content": task},
        ])


for cfg, label in [(SMALL, "dev"), (MEDIUM, "prod-Qwen"), (LARGE, "prod-cloud")]:
    node = GeneratorNode(LLMClient(cfg))
    resp = node("ну там клиентов")
    print(f"  env={label:12s}  model={cfg.model:30s}  SQL: {resp['text']}")
"""))

    cells.append(md("""\
        ## 5. Где LLM реально нужен (по проекту)

        Ноутбуки 01-09 показали Phase 1 (детерминированный аудитор). LLM
        нужен в **6 точках**:

        | Узел                   | Кто работает               | Почему не алгоритм                    |
        |------------------------|----------------------------|---------------------------------------|
        | **generator**          | ✅ LLM (Qwen-32B)          | NL→SQL по схеме — задача синтеза      |
        | **schema_link**        | ✅ Эмбеддинг (e5)          | Семантическая близость, не grep       |
        | **few-shot retrieval** | ✅ Эмбеддинг               | то же                                 |
        | **auditor Phase 2**    | ✅ LLM-судья (Qwen-32B)    | FP-фильтр + объяснение на русском     |
        | **reflector**          | ✅ LLM (Qwen-7B)           | Парафраз findings → урок              |
        | **dataset synthesis**  | ✅ LLM (одноразово, GPT-4o-mini) | SQL→NL back-translation               |

        Phase 1 (правила) — это **скелет**. LLM — **мускулы**.
        """))

    cells.append(eng_footer("06-on-prem-model-size"))
    return cells
