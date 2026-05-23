# Архитектура GreenData SQL Security System

> Картинка: [architecture.png](architecture.png) (рендер из [architecture.dot](architecture.dot) через `dot -Tpng`).
> Ниже — Mermaid-версии, которые рендерятся прямо в GitHub/IDE.

## Условные обозначения

| Цвет | Что значит |
|---|---|
| 🟦 голубой | детерминированный код (алгоритмы, без LLM) |
| 🟧 оранжевый | LLM-вызов |
| 🟩 зелёный | ML-эмбеддинги (не LLM) |
| ⬜ серый | инфраструктура / хранилище |

---

## 1. Высокоуровневый поток

```mermaid
flowchart LR
    U([Пользователь<br/>NL-задача]) --> UI[UI / API<br/>Streamlit + FastAPI]
    UI --> SYS[[Мультиагентная система<br/>генератор → судья → исправление]]
    SYS --> R([final_sql + audit_log])
    SYS -.трейсы.-> LF[(Langfuse)]
    SYS -.EXPLAIN, faker.-> PG[(Postgres sandbox)]
    SYS -.CWE/CAPEC/OWASP.-> RAG[(RAG store)]
```

---

## 2. Детальный граф (LangGraph)

```mermaid
flowchart TB
    U([NL-задача]) --> SL

    subgraph GRAPH["LangGraph StateGraph · PostgresSaver checkpoints"]
        direction TB
        SL["schema_link<br/>FAISS top-15 + FK-замыкание"]:::ml
        GEN["generator ●LLM<br/>Qwen-Coder 32B<br/>+ few-shot + reflection"]:::llm

        subgraph AUD["auditor (гибрид)"]
            direction TB
            P1["Phase 1 ○алгоритм<br/>pglast AST + EXPLAIN<br/>+ sensitive regex"]:::algo
            P2["Phase 2 ●LLM-судья<br/>триаж findings + RAG"]:::llm
            P1 -->|"findings"| P2
        end

        REF["reflector ●LLM<br/>Qwen-7B<br/>findings → Lesson"]:::llm
        FIN["finalize<br/>сборка SystemResult"]:::algo

        SL --> GEN
        GEN -->|"sql_candidate"| P1
        P2 -->|"approved · risk < 4.0"| FIN
        P2 -->|"not approved"| REF
        REF -.->|"state.reflection<br/>memory of mistakes"| GEN
    end

    FIN --> R([final_sql + audit_log])

    %% внешние сервисы
    SL <-.эмбеддинги схемы.-> RAG[(RAG store<br/>CWE/CAPEC/OWASP/PG-docs)]:::infra
    GEN <-.tools: get_schema<br/>get_samples<br/>few-shot.-> PG[(Postgres sandbox<br/>data_model.sql + faker)]:::infra
    P1 <-.EXPLAIN.-> PG
    P2 <-.search_rag_cwe<br/>lookup_capec.-> RAG
    GEN -.трейс.-> LF[(Langfuse self-host)]:::infra
    P2 -.трейс.-> LF
    REF -.трейс.-> LF

    classDef algo  fill:#B3E5FC,stroke:#039BE5,color:#01579B;
    classDef llm   fill:#FFE0B2,stroke:#FB8C00,color:#E65100;
    classDef ml    fill:#E8F5E9,stroke:#66BB6A,color:#1B5E20;
    classDef infra fill:#CFD8DC,stroke:#607D8B,color:#263238;
```

---

## 3. Слои: что детерминированно, что LLM

```mermaid
flowchart TB
    subgraph L4["Слой 4 — Оркестрация"]
        LG["LangGraph: state, переходы, persistence, retry"]:::algo
    end
    subgraph L3["Слой 3 — Агенты (LLM)"]
        A1["generator (Qwen-32B)"]:::llm
        A2["judge Phase 2 (Qwen-32B)"]:::llm
        A3["reflector (Qwen-7B)"]:::llm
    end
    subgraph L2["Слой 2 — Детерминированный аудит"]
        D1["pglast Visitor: R001-R013"]:::algo
        D2["EXPLAIN cost-checks"]:::algo
        D3["sensitive regex + Luhn/СНИЛС"]:::algo
    end
    subgraph L1["Слой 1 — ML-инфраструктура"]
        M1["эмбеддинги схемы (e5)"]:::ml
        M2["RAG retrieval (BM25+dense)"]:::ml
    end
    subgraph L0["Слой 0 — Хранилища"]
        S1["Postgres sandbox"]:::infra
        S2["RAG vector store"]:::infra
        S3["Langfuse"]:::infra
    end

    L4 --> L3 --> L2 --> L1 --> L0

    classDef algo  fill:#B3E5FC,stroke:#039BE5,color:#01579B;
    classDef llm   fill:#FFE0B2,stroke:#FB8C00,color:#E65100;
    classDef ml    fill:#E8F5E9,stroke:#66BB6A,color:#1B5E20;
    classDef infra fill:#CFD8DC,stroke:#607D8B,color:#263238;
```

---

## 4. Зоны ответственности команды (4 роли)

```mermaid
flowchart LR
    subgraph DATA["🗄️ Данные"]
        d1["schema_catalog.json"]
        d2["Postgres sandbox + faker"]
        d3["dataset_v1.jsonl"]
    end
    subgraph TOOLS["🔧 Тулы"]
        t1["pglast правила R001-R013"]
        t2["RAG-сборка CWE/CAPEC"]
        t3["plpgsql_check"]
    end
    subgraph LLM["🤖 LLM-инженер"]
        m1["LLMClient"]
        m2["generator / judge / reflector"]
        m3["LangGraph граф"]
    end
    subgraph ANALYST["📊 Аналитик"]
        a1["eval-pipeline (EX, Recall)"]
        a2["Langfuse + A/B"]
        a3["отчёт + презентация"]
    end

    DATA --> TOOLS
    DATA --> LLM
    TOOLS --> LLM
    LLM --> ANALYST
```

Подробности по ролям — будет в `docs/team_roles.md`.

---

## Контракты на стыках

| Стык | Контракт |
|---|---|
| UI → граф | `task: str → SystemResult` (`baseline1.py`) |
| generator → auditor | `sql: str + db_schema_meta` |
| Phase 1 → Phase 2 | `findings: list[Finding]` |
| auditor → reflector | `AuditResult` |
| reflector → generator | `state.reflection: list[Lesson]` |
| LLM-узлы → провайдер | OpenAI-compat `chat/completions` |
| RAG-tool → store | `search(query, top_k, filters) → list[Chunk]` |

Архитектурные обоснования — в [adr/](adr/).
