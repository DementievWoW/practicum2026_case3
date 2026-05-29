"""
@file service.py
@brief HTTP-сервис: POST /audit, GET /healthz, GET /metrics. Участник 4.

@details
    Это «дверь» наружу — то, что разворачивается в compose и видит пользователь.
    Под капотом — `run_instrumented` из runtime.py (пайплайн + метрики + трейсы).

    Endpoints
        POST /audit  {"task": "..."}        → SystemResult JSON + audit_log
        GET  /healthz                       → {"status":"ok"}  (для compose/k8s)
        GET  /metrics                       → текст Prometheus exposition

    Метрики поднимаются на :9100 при старте (стандартная практика — отдельный
    порт от бизнес-API, чтобы /metrics не торчал наружу через reverse-proxy).

    Запуск:
        uvicorn case3.infra.service:app --host 0.0.0.0 --port 8000
    Или через Dockerfile (CMD уже прописан).
"""
from __future__ import annotations

import json as _json
import os
import secrets
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from case3.infra import events as ev
from case3.infra import metrics as m
from case3.infra.runtime import run_instrumented


# ── auth: identity (X-User для всех) + Basic для админки ────────────────────
# Identity — никакой security, просто чтобы знать «кто Вася, кто Маша».
# Админка защищена единым ADMIN_USER / ADMIN_PASSWORD из env (compose).
def get_user(x_user: str | None = Header(default=None)) -> str:
    """@brief Идентификация по X-User header. anonymous если не задан."""
    return (x_user or "").strip()[:60] or "anonymous"


_admin_basic = HTTPBasic()


def require_admin(creds: HTTPBasicCredentials = Depends(_admin_basic)) -> str:
    """@brief HTTP Basic — для /admin/* endpoints. Креды из env."""
    expected_user = os.environ.get("ADMIN_USER", "admin")
    expected_pwd = os.environ.get("ADMIN_PASSWORD", "admin")
    ok_u = secrets.compare_digest(creds.username, expected_user)
    ok_p = secrets.compare_digest(creds.password, expected_pwd)
    if not (ok_u and ok_p):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid admin credentials",
                            headers={"WWW-Authenticate": "Basic"})
    return creds.username

# ─── метрики /metrics на :9100 поднимаются один раз при импорте модуля ──────
# (в multi-worker uvicorn каждый воркер поднимет свой порт → запускаем
# с --workers 1 в Dockerfile)
_METRICS_PORT = int(os.environ.get("METRICS_PORT", "9100"))
try:
    m.serve_metrics(port=_METRICS_PORT)
except OSError:
    # порт занят (например, повторный импорт в тестах) — не фатально
    pass

app = FastAPI(
    title="SQL Security Multi-Agent",
    description="NL→SQL с аудитом (gen→judge→fix loop). Артефакт: SQL + audit_log.",
    version="0.1.0",
)


class AuditRequest(BaseModel):
    """@brief Вход: NL-задача от пользователя."""
    task: str = Field(..., min_length=3, max_length=2000,
                      description="Описание задачи на естественном языке")
    max_iterations: int | None = Field(None, ge=1, le=10,
                                       description="Лимит итераций (по умолч. из baseline)")


class VulnOut(BaseModel):
    vuln_class: str
    risk_score: float
    description: str
    recommendation: str


class AuditResponse(BaseModel):
    """@brief Выход: то, что отдаём по контракту кейса (SQL + audit_log)."""
    final_sql: str
    approved: bool
    iterations_used: int
    risk_trajectory: list[float]
    vulnerabilities: list[VulnOut]
    audit_log: str
    metadata: dict[str, Any]


# ─── Каталог уязвимостей: 9 классов из ТЗ, для вкладки «Уязвимости» ─────────
# Каждый — название, badge (CRITICAL/DESTRUCTIVE/PII/INFO), risk, примеры
# SQL+NL, объяснение «почему опасно». Рендерится в HTML ниже.
_VULN_CATALOG: list[dict[str, Any]] = [
    {"code": "SQL_INJ_CLASSIC", "title": "Классическая SQL-инъекция",
     "alert": "CRITICAL", "risk": 9.0,
     "desc": "Внедрение SQL через незаэкранированный ввод (комментарии, тавтологии 'OR 1=1').",
     "sql": "SELECT * FROM users WHERE name = 'admin' OR '1'='1' --'",
     "nl":  "Найди пользователя admin с любым паролем",
     "why": "Условие WHERE становится всегда истинным → утечка всех строк таблицы."},
    {"code": "SQL_INJ_UNION", "title": "UNION-инъекция",
     "alert": "CRITICAL", "risk": 8.0,
     "desc": "Подклеивает чужой SELECT через UNION — выгребает данные из других таблиц.",
     "sql": "SELECT id FROM products WHERE id=1 UNION SELECT password FROM users",
     "nl":  "Покажи товар с id=1 и заодно вытяни пароли пользователей",
     "why": "Атакующий читает таблицы, к которым нет прямого доступа в эндпоинте."},
    {"code": "SQL_INJ_TIME", "title": "Time-based blind",
     "alert": "CRITICAL", "risk": 9.0,
     "desc": "Использует pg_sleep/CASE — задержка ответа выдаёт значение бита данных.",
     "sql": "SELECT 1 FROM users WHERE id=1 AND (CASE WHEN substr(password,1,1)='a' THEN pg_sleep(5) ELSE 0 END)",
     "nl":  "Подвисни на 5 сек если у админа пароль начинается с 'a'",
     "why": "Слепая эксфильтрация бита за битом — медленно, но без вывода в ответе."},
    {"code": "DML_NO_WHERE", "title": "UPDATE/DELETE без WHERE",
     "alert": "DESTRUCTIVE", "risk": 7.0,
     "desc": "Массовая модификация: WHERE забыт, удалён или экранирован комментарием.",
     "sql": "DELETE FROM credit_contract",
     "nl":  "Удали все договоры в credit_contract",
     "why": "Стирает или меняет всю таблицу — потеря бизнес-данных, восстановление только из бэкапа."},
    {"code": "PRIV_ESCALATE", "title": "Повышение прав / DDL",
     "alert": "DESTRUCTIVE", "risk": 10.0,
     "desc": "DROP/CREATE/ALTER, GRANT, ALTER USER — разрушение схемы или эскалация привилегий.",
     "sql": "DROP TABLE credit_contract",
     "nl":  "Удали таблицу credit_contract вместе со всеми данными",
     "why": "Уничтожение объектов БД или изменение прав — необратимо без бэкапа."},
    {"code": "PLPGSQL_UNSAFE", "title": "Динамический EXECUTE в функции",
     "alert": "CRITICAL", "risk": 8.0,
     "desc": "EXECUTE-конкатенация пользовательского input или SECURITY DEFINER без проверок.",
     "sql": "CREATE FUNCTION run(x text) RETURNS void LANGUAGE plpgsql AS $$ BEGIN EXECUTE 'DELETE FROM t WHERE id=' || x; END $$;",
     "nl":  "Сделай функцию-обёртку, принимающую id и удаляющую строку по нему",
     "why": "EXECUTE с конкатенацией = инъекция внутри функции, часто работает с правами owner-а."},
    {"code": "DIRECT_SENSITIVE", "title": "Прямой запрос PII (152-ФЗ)",
     "alert": "PII", "risk": 7.0,
     "desc": "SELECT/SHOW колонок с паспортами, СНИЛС, номерами карт, паролями.",
     "sql": "SELECT passport, snils, card_number FROM sim_client",
     "nl":  "Выгрузи паспорта, СНИЛС и номера карт всех клиентов",
     "why": "Утечка персональных данных → нарушение 152-ФЗ, штрафы, репутационный риск."},
    {"code": "SELECT_STAR", "title": "SELECT * без явных колонок",
     "alert": "INFO", "risk": 3.0,
     "desc": "Все колонки таблицы — может тянуть PII и перегружать сеть.",
     "sql": "SELECT * FROM credit_contract",
     "nl":  "Покажи все колонки договоров",
     "why": "Колонки таблицы могут меняться — запрос вернёт новые поля (включая PII) после ALTER."},
    {"code": "NO_PAGINATION", "title": "Запрос без LIMIT",
     "alert": "INFO", "risk": 2.0,
     "desc": "SELECT без LIMIT на потенциально большой таблице — нагрузка на БД и сеть.",
     "sql": "SELECT id, status FROM credit_contract",
     "nl":  "Покажи id и статус всех договоров",
     "why": "На таблице с миллионами строк — long query, забивает соединения и память клиента."},
]


def _render_vuln_pane() -> str:
    """@brief HTML-разметка вкладки «Уязвимости» (9 карточек)."""
    from html import escape as _h
    items = []
    for v in _VULN_CATALOG:
        risk = v["risk"]
        risk_cls = "vc-crit" if risk >= 7 else ("vc-warn" if risk >= 4 else "vc-low")
        badge_cls = "vc-" + v["alert"].lower()
        items.append(f'''
        <div class="vc-card {risk_cls}">
          <div class="vc-head">
            <span class="vc-badge {badge_cls}">{_h(v["alert"])}</span>
            <span class="vc-risk">risk <b>{risk:.1f}</b> / 10</span>
          </div>
          <div class="vc-code">{_h(v["code"])}</div>
          <div class="vc-title">{_h(v["title"])}</div>
          <div class="vc-desc">{_h(v["desc"])}</div>
          <div class="label" style="margin-top:10px">Пример SQL</div>
          <pre class="vc-sql">{_h(v["sql"])}</pre>
          <div class="vc-why"><b>Почему опасно:</b> {_h(v["why"])}</div>
          <div class="row" style="gap:6px;margin-top:12px">
            <button class="vc-try" data-q="{_h(v["nl"])}"
                    title="подставит NL-пример в поле «Аудит» — пройдёт через генератор + аудит"
                    style="flex:1">Вставить NL в поле</button>
            <button class="vc-audit" data-sql="{_h(v["sql"])}" data-label="{_h(v["code"])}"
                    title="отправит ЭТОТ SQL сразу в аудитор (без генератора) — гарантированно сработает класс"
                    style="flex:1">Сразу аудит этого SQL</button>
          </div>
        </div>''')
    return '<div class="vc-grid">' + "".join(items) + "</div>"


_UI_HTML = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>SQL Security Multi-Agent</title>
<style>
  :root { --bg:#0e1116; --fg:#e6edf3; --mut:#7d8590; --accent:#2f81f7;
          --ok:#3fb950; --warn:#d29922; --err:#f85149; --card:#161b22; }
  * { box-sizing:border-box }
  body { margin:0; font:14px/1.5 -apple-system,Segoe UI,Inter,sans-serif;
         background:var(--bg); color:var(--fg) }
  .wrap { max-width:1180px; margin:0 auto; padding:24px }
  h1 { margin:0 0 4px; font-size:22px }
  .sub { color:var(--mut); margin-bottom:24px }
  .card { background:var(--card); border:1px solid #30363d; border-radius:8px;
          padding:16px; margin-bottom:16px }
  textarea { width:100%; min-height:64px; background:#0d1117; color:var(--fg);
             border:1px solid #30363d; border-radius:6px; padding:10px;
             font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; resize:vertical }
  button { background:var(--accent); color:#fff; border:0; padding:8px 16px;
           border-radius:6px; cursor:pointer; font-weight:600 }
  button.ghost { background:transparent; border:1px solid #30363d; color:var(--fg) }
  button:disabled { opacity:.5; cursor:wait }
  .row { display:flex; gap:8px; margin-top:8px; flex-wrap:wrap; align-items:center }
  .chip { background:#21262d; border:1px solid #30363d; padding:4px 10px;
          border-radius:14px; font-size:12px; color:var(--mut); cursor:pointer }
  .chip:hover { color:var(--fg); border-color:var(--accent) }
  pre { background:#0d1117; padding:12px; border-radius:6px; overflow:auto;
        font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; max-height:300px }
  .ok { color:var(--ok) } .warn { color:var(--warn) } .err { color:var(--err) }
  .label { color:var(--mut); font-size:12px; text-transform:uppercase;
           letter-spacing:.5px; margin-bottom:4px }
  .vuln { border-left:3px solid var(--err); padding:6px 10px; margin:6px 0;
          background:#1c1f24; border-radius:4px }
  .vuln.low { border-left-color:var(--warn) }
  .meta { display:flex; gap:16px; flex-wrap:wrap; color:var(--mut); font-size:12px }
  .links { margin-top:24px; color:var(--mut); font-size:12px }
  .links a { color:var(--accent); text-decoration:none; margin-right:12px }
  /* tabs */
  .tabs { display:flex; gap:0; border-bottom:1px solid #30363d; margin-bottom:16px }
  .tab { padding:8px 16px; cursor:pointer; color:var(--mut); border-bottom:2px solid transparent;
         margin-bottom:-1px; font-size:13px }
  .tab.active { color:var(--fg); border-bottom-color:var(--accent) }
  .pane { display:none }
  .pane.active { display:block }
  /* result table */
  table.rs { width:100%; border-collapse:collapse; font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace }
  table.rs th, table.rs td { padding:6px 10px; border-bottom:1px solid #21262d; text-align:left;
                              white-space:nowrap; max-width:340px; overflow:hidden; text-overflow:ellipsis }
  table.rs th { color:var(--mut); font-weight:600; background:#0d1117; position:sticky; top:0 }
  .rs-wrap { max-height:420px; overflow:auto; border:1px solid #21262d; border-radius:6px }
  /* iframe */
  iframe { width:100%; border:1px solid #30363d; border-radius:6px; background:#0d1117 }
  /* chat */
  .msgs { display:flex; flex-direction:column; gap:12px; margin-bottom:12px }
  .msg { max-width:78%; padding:10px 14px; border-radius:10px; font-size:13px }
  .msg.user { align-self:flex-end; background:#1f2937; border:1px solid #30363d }
  .msg.bot  { align-self:flex-start; background:#161b22; border:1px solid #30363d }
  .msg.bot.clarify { border-left:3px solid var(--accent) }
  .msg.warn { align-self:stretch; background:#2b1d10; border:1px solid #d29922; color:#ffd28b }
  .options { display:flex; gap:6px; flex-wrap:wrap; margin-top:8px }
  .opt { background:#21262d; border:1px solid #30363d; color:var(--fg); padding:5px 10px;
         border-radius:14px; font-size:12px; cursor:pointer }
  .opt:hover { border-color:var(--accent) }
  .answer-row { display:flex; gap:6px; margin-top:8px }
  .answer-row input { flex:1; background:#0d1117; color:var(--fg); border:1px solid #30363d;
                       border-radius:6px; padding:6px 10px; font:13px ui-monospace,Menlo,monospace }
  /* user widget */
  .user-bar { position:fixed; top:8px; right:12px; background:#161b22;
              border:1px solid #30363d; border-radius:18px; padding:4px 10px 4px 4px;
              display:flex; align-items:center; gap:6px; font-size:12px; z-index:100 }
  .avatar { width:24px; height:24px; border-radius:50%; background:var(--accent);
            color:#fff; display:flex; align-items:center; justify-content:center;
            font-weight:700; font-size:11px }
  .user-bar a { color:var(--mut); text-decoration:none; cursor:pointer }
  .user-bar a:hover { color:var(--fg) }
  /* modal */
  .modal-bg { position:fixed; inset:0; background:rgba(0,0,0,.6); z-index:200;
              display:none; align-items:center; justify-content:center }
  .modal-bg.active { display:flex }
  .modal { background:var(--card); border:1px solid #30363d; border-radius:8px;
           padding:20px; min-width:340px; max-width:480px }
  .modal h3 { margin:0 0 8px; font-size:16px }
  .modal p { margin:0 0 12px; color:var(--mut); font-size:13px }
  .modal input { width:100%; padding:8px 10px; background:#0d1117; color:var(--fg);
                 border:1px solid #30363d; border-radius:6px; font:13px Menlo,monospace }
  /* admin */
  .stat-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:12px }
  .stat-num { font-size:32px; font-weight:700; color:var(--accent) }
  .stat-lbl { color:var(--mut); font-size:12px; text-transform:uppercase; letter-spacing:.5px }
  table.tt { width:100%; border-collapse:collapse; font-size:12px }
  table.tt th, table.tt td { padding:6px 8px; border-bottom:1px solid #21262d; text-align:left }
  table.tt th { color:var(--mut); font-weight:600 }
  /* feedback */
  .fb-btn { background:#21262d; border:1px solid #30363d; color:var(--fg);
            padding:8px 14px; border-radius:6px; cursor:pointer; font-size:14px;
            transition:all .15s }
  .fb-btn:hover { border-color:var(--accent) }
  .fb-btn.up.active { background:#1a4a2a; border-color:var(--ok); color:var(--ok) }
  .fb-btn.down.active { background:#4a1a1a; border-color:var(--err); color:var(--err) }
  .fb-comment { width:100%; margin-top:8px; background:#0d1117; color:var(--fg);
                border:1px solid #30363d; border-radius:6px; padding:8px 10px;
                font:13px ui-monospace,Menlo,monospace; min-height:50px; resize:vertical }
  .fb-thanks { color:var(--ok); font-size:13px; margin-top:8px }
  /* thinking */
  .think { font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--mut);
           padding-left:24px; border-left:2px dashed #30363d; margin:6px 0 12px 4px }
  .think .step { padding:3px 0; opacity:0; animation:fadeIn .25s forwards }
  @keyframes fadeIn { to { opacity: 1 } }
  .think .step.gen  { color:#79c0ff }
  .think .step.aud  { color:#ffa657 }
  .think .step.ref  { color:#d2a8ff }
  .think .step.iter { color:var(--fg); font-weight:600; margin-top:6px }
  .think .step.err  { color:var(--err) }
  .think .step .t   { color:var(--mut); font-size:11px; margin-left:6px }
  .think pre { background:#0d1117; padding:6px 10px; border-radius:4px;
               margin:4px 0; max-height:100px; overflow:auto; font-size:11px }
  /* explain analyze tree */
  .plan-head { display:flex; gap:18px; flex-wrap:wrap; font:13px ui-monospace,Menlo,monospace;
               padding:8px 10px; background:#0d1117; border-radius:6px; margin-bottom:8px }
  .plan-head b { color:var(--fg); font-size:14px }
  .plan-tree { font:12px ui-monospace,SFMono-Regular,Menlo,monospace }
  .plan-node { display:grid; grid-template-columns:110px 1fr; gap:10px;
               padding:4px 8px; border-bottom:1px solid #21262d; align-items:baseline }
  .plan-node:last-child { border-bottom:0 }
  .plan-time { font-weight:700; text-align:right }
  .plan-time.ok   { color:var(--ok) }
  .plan-time.warn { color:var(--warn) }
  .plan-time.err  { color:var(--err) }
  .plan-pct { color:var(--mut); font-weight:400; font-size:11px; margin-left:4px }
  .plan-row { color:var(--fg) }
  .plan-rel { color:#79c0ff }
  .plan-info { color:var(--mut); font-size:11px; margin-top:2px }
  .explain-tog { vertical-align:middle; margin:0 4px 0 0 }
  /* vuln catalog */
  .vc-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:14px }
  .vc-card { background:var(--card); border:1px solid #30363d; border-left:3px solid var(--ok);
             border-radius:8px; padding:14px; display:flex; flex-direction:column }
  .vc-card.vc-warn { border-left-color:var(--warn) }
  .vc-card.vc-crit { border-left-color:var(--err) }
  .vc-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px }
  .vc-badge { font-size:11px; font-weight:700; letter-spacing:.5px; padding:3px 8px;
              border-radius:10px; text-transform:uppercase }
  .vc-critical, .vc-destructive { background:#4a1a1a; color:#ffb4b4; border:1px solid var(--err) }
  .vc-pii { background:#3a2515; color:#ffd28b; border:1px solid var(--warn) }
  .vc-info { background:#1a3a4a; color:#7ed4ff; border:1px solid #7ed4ff }
  .vc-risk { color:var(--mut); font-size:12px; font-family:ui-monospace,Menlo,monospace }
  .vc-risk b { color:var(--fg) }
  .vc-code { font:11px ui-monospace,Menlo,monospace; color:var(--mut); margin-bottom:4px }
  .vc-title { font-size:15px; font-weight:600; margin-bottom:6px }
  .vc-desc { color:var(--mut); font-size:13px; margin-bottom:6px }
  .vc-sql { font-size:11px; max-height:120px; margin-top:4px }
  .vc-why { font-size:12px; color:var(--mut); margin-top:10px; padding:8px 10px;
            background:#0d1117; border-radius:4px; border-left:2px solid #30363d }
  .vc-try { margin-top:12px; background:#21262d; border:1px solid #30363d; color:var(--fg);
            padding:8px 12px; border-radius:6px; cursor:pointer; font-size:13px; width:100% }
  .vc-try:hover { border-color:var(--accent); color:var(--accent) }
  /* prediction card */
  .pc-row { display:grid; grid-template-columns:120px 1fr; gap:12px; padding:4px 0;
            font:13px ui-monospace,Menlo,monospace; align-items:baseline }
  .pc-row .k { color:var(--mut); font-size:11px; text-transform:uppercase; letter-spacing:.5px }
  .pc-row .v b { color:var(--fg); font-size:14px }
  .pc-hint { font-size:12px; color:var(--warn); padding:4px 8px; margin:4px 0;
             background:#2a1f08; border-left:2px solid var(--warn); border-radius:3px }
  .pc-tree { font:12px ui-monospace,Menlo,monospace; color:var(--mut); margin-top:6px }
  .pc-tree div { padding:2px 0 }
  .pc-tree .rel { color:#79c0ff }
  .pc-help { margin-top:14px; padding-top:12px; border-top:1px dashed #30363d }
  .pc-help .label { margin-bottom:8px }
  .pc-snippet { background:#0d1117; border:1px solid #30363d; border-radius:6px;
                padding:10px; margin:8px 0; font:12px ui-monospace,Menlo,monospace;
                white-space:pre; overflow-x:auto }
  .pc-snippet .cm { color:var(--mut) }
  .pc-snippet .kw { color:#ff7b72 }
  .pc-report { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-top:10px }
  .pc-report input { background:#0d1117; color:var(--fg); border:1px solid #30363d;
                     border-radius:6px; padding:6px 10px; font:13px Menlo,monospace; width:110px }
  .pc-diff { font:12px ui-monospace,Menlo,monospace; padding:2px 8px; border-radius:10px }
  .pc-diff.ok { background:#0d2818; color:var(--ok); border:1px solid var(--ok) }
  .pc-diff.err { background:#28100d; color:var(--err); border:1px solid var(--err) }
</style></head>
<body><div class="wrap">
  <h1>SQL Security · Multi-Agent</h1>
  <div class="sub">NL→SQL с аудитом. Цикл «генератор → судья → reflection-фикс».
      Артефакт: SQL + audit log (без исполнения на проде). Кнопка «Выполнить»
      на этой странице — ТОЛЬКО для демо на seed-БД.</div>

  <!-- user-bar: identity справа сверху -->
  <div class="user-bar" id="user-bar" style="display:none">
    <div class="avatar" id="user-avatar">?</div>
    <span id="user-name">…</span>
    <a id="user-change">сменить</a>
  </div>

  <!-- модалка ввода имени -->
  <div class="modal-bg" id="user-modal">
    <div class="modal">
      <h3>Как вас зовут?</h3>
      <p>Просто имя — оно прикрепляется к запросам для статистики.
         Это не пароль, не делает запросы безопаснее. Можно сменить позже.</p>
      <input id="user-input" type="text" placeholder="напр.: vasya" autocomplete="off">
      <div class="row" style="justify-content:flex-end;margin-top:12px">
        <button id="user-save">Сохранить</button>
      </div>
    </div>
  </div>

  <div class="tabs">
    <div class="tab active" data-pane="audit">Аудит</div>
    <div class="tab" data-pane="vulns">Уязвимости</div>
    <div class="tab" data-pane="grafana">Grafana</div>
    <div class="tab" data-pane="langfuse">Langfuse</div>
    <div class="tab" data-pane="admin">Админка</div>
  </div>

  <!-- ─── Pane: Аудит (chat-стиль) ───────────────────────────────────────── -->
  <div class="pane active" id="pane-audit">
    <div class="card">
      <div class="label">NL-задача (новый диалог)</div>
      <textarea id="task" placeholder="напр.: Удали старые черновики заявок"></textarea>
      <div class="row">
        <button id="go" title="Live SSE: видно поток «мыслей» пайплайна">🧠 Начать (Live)</button>
        <button class="ghost" id="reset" style="display:none">Сбросить диалог</button>
        <span class="chip" data-q="Сколько кредитных договоров?">агрегат</span>
        <span class="chip" data-q="Топ-5 компаний по числу договоров (count desc, name asc): name, count">join+top-N</span>
        <span class="chip" data-q="Удали старые черновики заявок">DELETE (clarify)</span>
        <span class="chip" data-q="Покажи активных клиентов">«активный» (clarify)</span>
        <span class="chip" data-q="Покажи всё про клиентов">провокация: SELECT *</span>
        <span class="chip" data-q="Покажи все таблицы базы данных из pg_catalog">провокация: pg_catalog</span>
      </div>
    </div>
    <div id="msgs" class="msgs"></div>
    <div id="out"></div>
  </div>

  <!-- ─── Pane: Каталог уязвимостей ───────────────────────────────────────── -->
  <div class="pane" id="pane-vulns">
    <div class="card">
      <div class="label">Каталог уязвимостей (9 классов из ТЗ)</div>
      <p style="color:var(--mut);font-size:13px;margin:6px 0 0">
        Левая полоса карточки — уровень риска:
        <span style="color:var(--ok)">зелёная INFO</span> ·
        <span style="color:var(--warn)">оранжевая PII / средний</span> ·
        <span style="color:var(--err)">красная CRITICAL / DESTRUCTIVE</span>.
        Кнопка <b>«Вставить пример в аудит»</b> подставит NL-вариант в поле на вкладке «Аудит»,
        а запускать цикл (или сначала отредактировать) — уже вам.
      </p>
    </div>
    <!-- VULN_CARDS -->
  </div>

  <!-- ─── Pane: Grafana iframe ────────────────────────────────────────────── -->
  <div class="pane" id="pane-grafana">
    <div class="card">
      <div class="row" style="justify-content:space-between">
        <div>
          <div class="label">Дашборд SQL Security</div>
          <small class="ok">runs / latency / risk gauge / findings by vuln_class</small>
        </div>
        <a href="http://localhost:13000/d/sqlsec-main?kiosk=tv" target="_blank">
          <button class="ghost">Открыть в Grafana →</button>
        </a>
      </div>
    </div>
    <iframe id="grafana-frame"
            src="http://localhost:13000/d/sqlsec-main?orgId=1&refresh=10s&kiosk=tv&theme=dark"
            height="720"></iframe>
  </div>

  <!-- ─── Pane: Langfuse (без iframe — CSP frame-ancestors=none) ───────────── -->
  <div class="pane" id="pane-langfuse">
    <div class="card">
      <div class="label">Langfuse — трейсы LLM-цепочек</div>
      <p style="color:var(--mut);font-size:13px;margin:8px 0">
        Langfuse self-host блокирует встраивание через iframe (CSP frame-ancestors=none).
        После прогона из таба «Аудит» здесь появится прямая ссылка на trace.
      </p>
      <div id="lf-hint" class="warn">пока трейсов нет — запусти любой аудит сначала</div>
      <div class="row" style="margin-top:12px">
        <a href="http://localhost:13001/traces" target="_blank">
          <button>Открыть список trace'ов →</button>
        </a>
        <a href="http://localhost:13001" target="_blank">
          <button class="ghost">Главная Langfuse →</button>
        </a>
      </div>
    </div>
  </div>

  <!-- ─── Pane: Админка ──────────────────────────────────────────────────── -->
  <div class="pane" id="pane-admin">
    <div class="card" id="admin-login-card">
      <div class="label">Админ-доступ нужен для статистики и выгрузки</div>
      <p style="color:var(--mut);font-size:13px;margin:8px 0">
        HTTP Basic Auth. Креды — из <code>ADMIN_USER</code> / <code>ADMIN_PASSWORD</code>
        в .env (по умолч. <code>admin</code>/<code>admin</code> для локального демо).
      </p>
      <div class="row" style="margin-top:8px">
        <input type="text" id="admin-user" placeholder="admin" style="background:#0d1117;color:var(--fg);border:1px solid #30363d;border-radius:6px;padding:6px 10px;font:13px Menlo,monospace">
        <input type="password" id="admin-pwd" placeholder="••••••" style="background:#0d1117;color:var(--fg);border:1px solid #30363d;border-radius:6px;padding:6px 10px;font:13px Menlo,monospace">
        <button id="admin-login">Войти</button>
        <button class="ghost" id="admin-logout" style="display:none">Выйти</button>
      </div>
      <div id="admin-err" class="err" style="display:none;margin-top:8px"></div>
    </div>
    <div id="admin-content" style="display:none"></div>
  </div>

  <div class="links">
    <a href="/docs">/docs (OpenAPI)</a>
    <a href="/metrics">/metrics</a>
    <a href="http://localhost:13000" target="_blank">Grafana ↗</a>
    <a href="http://localhost:13001" target="_blank">Langfuse ↗</a>
    <a href="http://localhost:19090" target="_blank">Prometheus ↗</a>
  </div>
</div>

<script>
// Глобальный обработчик ошибок: рисуем баннер сверху, чтобы видеть
// JS-ошибки даже без открытой DevTools. Полезно для коллег-новичков.
window.addEventListener('error', e => {
  const banner = document.getElementById('js-err-banner') || (() => {
    const b = document.createElement('div');
    b.id = 'js-err-banner';
    b.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;'
                    + 'background:#f85149;color:#fff;padding:10px;font:13px monospace;'
                    + 'max-height:200px;overflow:auto';
    document.body.prepend(b);
    return b;
  })();
  banner.textContent = `JS ERROR: ${e.message} @ ${e.filename}:${e.lineno}:${e.colno}`;
});

const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const out = $('#out');

// ── identity (X-User для всех запросов) ──
let _user = localStorage.getItem('sqlsec_user') || '';
let _adminAuth = sessionStorage.getItem('sqlsec_admin_auth') || '';

function showUserBar() {
  const bar = $('#user-bar');
  if (!_user) { bar.style.display = 'none'; return; }
  bar.style.display = '';
  $('#user-name').textContent = _user;
  $('#user-avatar').textContent = (_user[0] || '?').toUpperCase();
}
function openUserModal() {
  $('#user-modal').classList.add('active');
  $('#user-input').value = _user || '';
  setTimeout(() => $('#user-input').focus(), 50);
}
function saveUser() {
  const v = $('#user-input').value.trim();
  if (!v) return;
  _user = v.slice(0, 60);
  localStorage.setItem('sqlsec_user', _user);
  showUserBar();
  $('#user-modal').classList.remove('active');
}
$('#user-save').onclick = saveUser;
$('#user-input').addEventListener('keydown', e => { if (e.key === 'Enter') saveUser(); });
$('#user-change').onclick = openUserModal;
// при первом заходе — модалка
if (!_user) openUserModal(); else showUserBar();

// Обёртка над fetch: добавляет X-User
const _origFetch = window.fetch.bind(window);
window.fetch = (url, opts = {}) => {
  const h = new Headers(opts.headers || {});
  if (_user) h.set('X-User', _user);
  // для /admin/* — Basic auth из sessionStorage
  if (typeof url === 'string' && url.startsWith('/admin') && _adminAuth) {
    h.set('Authorization', 'Basic ' + _adminAuth);
  }
  return _origFetch(url, {...opts, headers: h});
};

// ── tabs ──
$$('.tab').forEach(t => {
  t.onclick = () => {
    $$('.tab').forEach(x => x.classList.remove('active'));
    $$('.pane').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    $('#pane-' + t.dataset.pane).classList.add('active');
  };
});

// ── chips: подставляют пример в поле, НЕ запускают авто (как и vc-try) ──
$$('.chip').forEach(c => {
  // у чек-боксов внутри .chip уже есть свой data-q? пропустим тоггл-чипы
  if (!c.dataset.q) return;
  c.onclick = () => {
    const t = $('#task');
    if (!t) return;
    t.value = c.dataset.q;
    t.focus();
    t.setSelectionRange(t.value.length, t.value.length);
    t.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };
});

// ── persist explain-toggle state ──
document.addEventListener('change', e => {
  if (e.target.classList && e.target.classList.contains('explain-tog')) {
    localStorage.setItem('explain', e.target.checked ? '1' : '');
  }
});

// ── catalog: «Вставить NL в поле» (через генератор) ──
document.addEventListener('click', e => {
  if (e.target.classList && e.target.classList.contains('vc-try')) {
    const q = e.target.dataset.q;
    document.querySelector(".tab[data-pane='audit']").click();
    const t = $('#task');
    if (t) {
      t.value = q;
      t.focus();
      t.setSelectionRange(t.value.length, t.value.length);
      t.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
});

// ── catalog: «Сразу аудит этого SQL» (минуя генератор) ──
document.addEventListener('click', async e => {
  if (!e.target.classList || !e.target.classList.contains('vc-audit')) return;
  const sql = e.target.dataset.sql;
  const label = e.target.dataset.label || 'audit-sql';
  if (!sql) return;
  document.querySelector(".tab[data-pane='audit']").click();
  resetDialog();
  _task = '[' + label + '] ' + sql;
  renderUser('Прямой аудит примера: ' + label);
  out.innerHTML = '<div class="card">… аудитор проверяет SQL из карточки …</div>';
  try {
    const r = await fetch('/audit-sql', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ sql, label })
    });
    if (!r.ok) {
      const err = await r.text();
      out.innerHTML = `<div class="card err">HTTP ${r.status}: ${esc(err)}</div>`;
      return;
    }
    const d = await r.json();
    // Подмешаем поля до тех, что ожидает chat-sql ветка рендера:
    d.trace_id = (d.metadata && d.metadata.trace_id) || null;
    _lastSQL = d.final_sql; _lastApproved = d.approved;
    const verdict = d.approved
      ? '<span class="ok">approved</span>'
      : '<span class="err">rejected</span>';
    const traj = (d.risk_trajectory || []).map(x => x.toFixed(1)).join(' → ');
    const pms = ((d.metadata && d.metadata.pipeline_ms) || 0).toFixed(0);
    renderBot(`SQL из каталога (${esc(label)}) · ${verdict} · риск <b>${traj}</b> · аудит <b>${pms} мс</b>`);
    const vulnsHtml = (d.vulnerabilities || []).map(v => `
      <div class="vuln ${v.risk_score < 4 ? 'low':''}">
        <b>${esc(v.vuln_class)}</b> · risk ${v.risk_score.toFixed(1)}<br>
        ${esc(v.description)}<br>
        <small class="ok">↳ ${esc(v.recommendation || '')}</small>
      </div>`).join('') || '<div class="ok">уязвимостей не найдено</div>';
    out.innerHTML = `
      <div class="card">
        <div class="label">SQL из каталога (${esc(label)})</div>
        <pre>${esc(d.final_sql)}</pre>
      </div>
      <div class="card">
        <div class="label">Уязвимости</div>
        ${vulnsHtml}
      </div>
      <div class="card">
        <div class="label">Audit log</div>
        <pre>${esc(d.audit_log)}</pre>
      </div>`;
    $('#reset').style.display = '';
  } catch (err) {
    out.innerHTML = `<div class="card err">network: ${esc(err.message)}</div>`;
  }
});

function esc(s) { return String(s ?? '').replace(/[&<>]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

// ── EXPLAIN ANALYZE: чекбокс + рендер дерева плана ─────────────────────
function explainCheckbox() {
  const on = localStorage.getItem('explain') === '1' ? 'checked' : '';
  return `<label class="chip" style="cursor:pointer;user-select:none" title="EXPLAIN (ANALYZE) — Postgres вернёт реальное время на каждом узле плана"><input type="checkbox" class="explain-tog" ${on}> 🔬 разбивка по операциям</label>`;
}
function renderPlan(plan) {
  if (!plan || !plan['Plan']) return '';
  const exec = +plan['Execution Time'] || 0;
  const planTime = +plan['Planning Time'] || 0;
  function node(n, depth) {
    const t = +n['Actual Total Time'] || 0;
    const rows = n['Actual Rows'];
    const erows = n['Plan Rows'];
    const cost = +n['Total Cost'] || 0;
    const type = n['Node Type'] || '?';
    const rel = n['Relation Name'] ? ` <span class="plan-rel">${esc(n['Relation Name'])}</span>` : '';
    const heat = exec ? (t/exec > 0.5 ? 'err' : (t/exec > 0.2 ? 'warn' : 'ok')) : 'ok';
    const pct = exec ? ` <span class="plan-pct">${(t/exec*100).toFixed(0)}%</span>` : '';
    const indent = '│ '.repeat(Math.max(0, depth-1)) + (depth ? '└─ ' : '');
    const extra = (rows != null && erows != null && erows > 0 && (rows/erows > 10 || rows/erows < 0.1))
        ? ` <span class="err">[оценка ×${(rows/erows).toFixed(1)}]</span>` : '';
    let html = `<div class="plan-node">
      <div class="plan-time ${heat}">${t.toFixed(2)} мс${pct}</div>
      <div>
        <div class="plan-row">${esc(indent)}${esc(type)}${rel}</div>
        <div class="plan-info">${rows ?? '?'} строк (план: ${erows ?? '?'})${extra} · cost ${cost.toFixed(0)}</div>
      </div>
    </div>`;
    (n['Plans'] || []).forEach(c => html += node(c, depth+1));
    return html;
  }
  return `
    <div class="card">
      <div class="label">⏱ Тайминг (EXPLAIN ANALYZE)</div>
      <div class="plan-head">
        <span><b>Execution: ${exec.toFixed(2)} мс</b></span>
        <span>Planning: ${planTime.toFixed(2)} мс</span>
        <span class="ok">красная узлы = «горячее место» (>50% времени)</span>
      </div>
      <div class="plan-tree">${node(plan['Plan'], 0)}</div>
    </div>`;
}

// ── Аналитический прогноз времени + «хочу помочь» обратная связь ────────────
// Карточка появляется после approved SQL. async-fetch /predict-time → cost,
// план, подсказки. Чекбокс «🤝 хочу помочь» открывает SQL-обёртки для замера
// на боевой БД (EXPLAIN ANALYZE + pg_stat_statements). Юзер вводит реальное
// время → POST /timing/report → пара (cost, real_ms) пишется в jsonl.
function renderPredictionCard(sql, traceId) {
  return `
    <div class="card" id="pc-card" data-sql="${esc(sql)}" data-trace="${esc(traceId || '')}">
      <div class="label">⏱ Аналитический прогноз времени</div>
      <div id="pc-out" style="color:var(--mut);font-size:13px">… анализирую план …</div>

      <div class="pc-help">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px">
          <div class="label" style="margin:0">Команда для запуска у вас на БД</div>
          <label class="chip" style="cursor:pointer;user-select:none">
            <input type="checkbox" id="pc-help-tog" style="vertical-align:middle;margin-right:6px">
            🤝 Хочу помочь обучить (обернёт в EXPLAIN ANALYZE)
          </label>
        </div>
        <div id="pc-cmd-hint" style="font-size:12px;color:var(--mut);margin-bottom:6px"></div>
        <div class="pc-snippet" id="pc-cmd-code"></div>
        <div class="row" style="margin-top:8px">
          <button class="ghost" id="pc-copy">📋 Скопировать</button>
        </div>
      </div>

      <div id="pc-report-block" style="display:none;margin-top:14px;padding-top:12px;border-top:1px dashed #30363d">
        <div class="label">📝 Отчёт о реальном времени</div>
        <div style="font-size:12px;color:var(--mut);margin-bottom:8px">
          Вставь сюда <b>весь вывод EXPLAIN ANALYZE</b> (или просто фрагмент с
          <code>"Execution Time"</code>) — мы сами выдернем число. Или впиши вручную ниже.
        </div>
        <textarea id="pc-explain-paste" rows="4" placeholder='Вставь сюда вывод psql целиком. Пример: [{"Plan": {...}, "Execution Time": 12.345}]'
                  style="width:100%;background:#0d1117;color:var(--fg);border:1px solid #30363d;border-radius:6px;padding:8px;font:12px ui-monospace,Menlo,monospace;resize:vertical"></textarea>
        <div style="font-size:11px;color:var(--mut);margin:4px 0 10px" id="pc-explain-parsed">— нет вывода —</div>
        <div class="pc-report">
          <span class="label" style="margin:0">Реальное время:</span>
          <input type="number" id="pc-real-ms" placeholder="мс" step="0.1" min="0">
          <select id="pc-source" style="background:#0d1117;color:var(--fg);border:1px solid #30363d;border-radius:6px;padding:6px 8px;font:13px Menlo,monospace">
            <option value="explain_analyze">из EXPLAIN ANALYZE</option>
            <option value="pg_stat_statements">из pg_stat_statements</option>
            <option value="manual">руками (psql \\timing)</option>
          </select>
          <button id="pc-report-btn">Отправить отчёт</button>
          <span id="pc-report-result" style="font-size:12px"></span>
        </div>
      </div>

      <div id="pc-trace-bottom" style="display:none;margin-top:14px;padding-top:10px;border-top:1px solid #21262d;font-size:12px;color:var(--mut)">
        ↳ <a id="pc-trace-link" href="#" target="_blank" style="color:var(--accent);text-decoration:none">Открыть трейс пайплайна в Langfuse →</a>
      </div>
    </div>`;
}
function _firstTable(sql) {
  const m = String(sql || '').match(/\\bfrom\\s+([a-zA-Z_][\\w.]*)/i);
  return m ? m[1].replace(/^public\\./, '') : 'your_table';
}
async function bindPredictionCard(sql, traceId) {
  const out = $('#pc-out');
  if (!out) return;
  try {
    const r = await fetch('/predict-time', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sql})
    });
    const d = await r.json();
    if (d.error) {
      // прогноз не получился — показываем причину, но команду ниже всё равно заполняем
      out.innerHTML = `<span class="warn">⚠ прогноз не построен: ${esc(d.error)}</span>
        <div style="margin-top:4px;font-size:12px;color:var(--mut)">${esc(d.note || '')}</div>`;
    } else {
    const hintsHtml = (d.hints || []).map(h => `<div class="pc-hint">⚠ ${esc(h)}</div>`).join('');
    const tree = (d.plan_tree || []).map(n =>
      `<div>${'  '.repeat(n.depth)}└─ ${esc(n.node_type)}` +
      (n.relation ? ` <span class="rel">${esc(n.relation)}</span>` : '') +
      ` <span style="color:var(--mut)">· ${n.rows} строк · cost ${n.cost.toFixed(0)}</span></div>`
    ).join('');
    out.innerHTML = `
      <div class="pc-row"><span class="k">Plan cost</span>
        <span class="v"><b>${d.cost.toFixed(0)}</b> <small>(на demo_db)</small></span></div>
      <div class="pc-row"><span class="k">Прогноз ms</span>
        <span class="v"><b>~${d.predicted_ms_lo.toFixed(1)} – ${d.predicted_ms_hi.toFixed(1)} мс</b>
          <small style="color:var(--mut)"> · диапазон широкий, нужны отчёты для калибровки</small></span></div>
      <div class="pc-row"><span class="k">План</span>
        <span class="v">${esc(d.plan_summary)} · ${d.rows_estimate} строк (оценка)</span></div>
      ${hintsHtml ? `<div style="margin-top:8px">${hintsHtml}</div>` : ''}
      <details style="margin-top:8px"><summary style="cursor:pointer;color:var(--mut);font-size:12px">показать дерево плана</summary>
        <div class="pc-tree">${tree}</div></details>
      <div style="margin-top:6px;font-size:11px;color:var(--mut)">${esc(d.note)}</div>`;
    // запомним результат на карточке для submitTimingReport
    const card = $('#pc-card');
    if (card) {
      card.dataset.cost = d.cost;
      card.dataset.lo = d.predicted_ms_lo;
      card.dataset.hi = d.predicted_ms_hi;
    }
    }  // end of else (no d.error)
  } catch (e) {
    out.innerHTML = `<span class="err">не удалось получить прогноз: ${esc(e.message)}</span>`;
  }
  // команда + тоггл — переключает plain ↔ wrapped (EXPLAIN ANALYZE);
  // отчёт открывается только в режиме «обёрнуто».
  const tog = $('#pc-help-tog');
  const reportBlock = $('#pc-report-block');
  const code = $('#pc-cmd-code');
  const hint = $('#pc-cmd-hint');
  const copyBtn = $('#pc-copy');
  const sqlClean = String(sql || '').trim().replace(/;+$/, '');
  function _updateCmdView() {
    if (!code || !hint) return;
    const wrapped = tog && tog.checked;
    if (wrapped) {
      code.innerHTML = '<span class="kw">EXPLAIN</span> (<span class="kw">ANALYZE</span>, <span class="kw">BUFFERS</span>, <span class="kw">FORMAT</span> <span class="kw">JSON</span>)\\n' + esc(sqlClean) + ';';
      hint.innerHTML = 'скопируй и запусти у себя → Postgres вернёт <b>Execution Time</b> → впиши его в отчёт ниже';
      if (reportBlock) reportBlock.style.display = '';
    } else {
      code.innerHTML = esc(sqlClean) + ';';
      hint.innerHTML = 'скопируй и запусти у себя — отчёт необязателен';
      if (reportBlock) reportBlock.style.display = 'none';
    }
  }
  _updateCmdView();
  if (tog) tog.onchange = _updateCmdView;
  if (copyBtn) {
    copyBtn.onclick = async () => {
      const text = (tog && tog.checked)
        ? 'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)\\n' + sqlClean + ';'
        : sqlClean + ';';
      try {
        await navigator.clipboard.writeText(text);
        const old = copyBtn.innerHTML;
        copyBtn.textContent = '✓ скопировано';
        setTimeout(() => { copyBtn.innerHTML = old; }, 1500);
      } catch (e) {
        copyBtn.textContent = '⚠ ' + (e.message || 'fail');
      }
    };
  }
  const reportBtn = $('#pc-report-btn');
  if (reportBtn) reportBtn.onclick = submitTimingReport;

  // авто-парсинг вставленного EXPLAIN-вывода: ищем "Execution Time": NUMBER
  const pasteEl = $('#pc-explain-paste');
  const parsedEl = $('#pc-explain-parsed');
  const realEl = $('#pc-real-ms');
  const srcEl = $('#pc-source');
  function _parsePaste() {
    if (!pasteEl || !parsedEl) return;
    const raw = pasteEl.value || '';
    if (!raw.trim()) { parsedEl.innerHTML = '— нет вывода —'; return; }
    // ловим разные форматы: JSON ("Execution Time": 3.56),
    // psql text (Execution Time: 3.56 ms), наш рендер (Execution: 3.56 мс)
    const mExec = raw.match(/"?Execution(?:\\s+Time)?"?\\s*:\\s*([\\d.]+)/i);
    const mPlan = raw.match(/"?Planning(?:\\s+Time)?"?\\s*:\\s*([\\d.]+)/i);
    if (mExec) {
      const ms = parseFloat(mExec[1]);
      if (realEl) realEl.value = ms;
      if (srcEl) srcEl.value = 'explain_analyze';
      const planStr = mPlan ? ` · Planning: ${parseFloat(mPlan[1]).toFixed(2)} мс` : '';
      parsedEl.innerHTML = `<span class="ok">✓ распарсил Execution Time = <b>${ms.toFixed(3)} мс</b>${planStr}</span>`;
    } else {
      parsedEl.innerHTML = '<span class="warn">не нашёл "Execution Time" — впиши вручную ниже</span>';
    }
  }
  if (pasteEl) {
    pasteEl.addEventListener('input', _parsePaste);
    pasteEl.addEventListener('paste', () => setTimeout(_parsePaste, 0));
  }

  // линк на трейс внизу карточки
  const traceBottom = $('#pc-trace-bottom');
  const traceLink = $('#pc-trace-link');
  if (traceId && traceBottom && traceLink) {
    traceLink.href = 'http://localhost:13001/trace/' + traceId;
    traceLink.textContent = 'Открыть трейс ' + traceId.slice(0, 8) + ' в Langfuse →';
    traceBottom.style.display = '';
  }
}
// (renderHelpBlock удалён — устаревший каркас песочницы с дублирующими ID;
// актуальный UI собирается из renderSandboxCard + renderPredictionCard)
function renderSandboxCard(sql) {
  return `
    <div class="card" id="sb-card" data-sql="${esc(sql)}">
      <div class="label">🧪 Песочница — тестовая БД (demo_db)</div>
      <div style="font-size:12px;color:var(--mut);margin-bottom:8px">
        Свободный SQL на нашей demo_db (60 таблиц, faker, 500 строк/таблица). Поддерживается
        <b>EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) …</b> — Postgres вернёт реальное время.
        Цифры локальные, не репрезентативны для прода — для своей БД используй команду из карточки прогноза выше.
      </div>
      <textarea id="sb-sql" rows="5" placeholder="EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)&#10;SELECT count(*) FROM credit_contract;" style="width:100%;background:#0d1117;color:var(--fg);border:1px solid #30363d;border-radius:6px;padding:10px;font:13px ui-monospace,SFMono-Regular,Menlo,monospace;resize:vertical"></textarea>
      <div class="row" style="margin-top:8px">
        <button id="sb-run">Выполнить</button>
        <button class="ghost" id="sb-fill" title="подставит финальный SQL сверху">📋 Вставить финальный SQL</button>
      </div>
      <div id="sb-out" style="margin-top:12px"></div>
    </div>`;
}
function bindSandboxCard(sql) {
  const sbRun = $('#sb-run');
  const sbFill = $('#sb-fill');
  if (sbRun) sbRun.onclick = runSandboxSQL;
  if (sbFill && sql) sbFill.onclick = () => { const t = $('#sb-sql'); if (t) t.value = sql; };
}
async function runSandboxSQL() {
  const sqlEl = $('#sb-sql');
  const out = $('#sb-out');
  const btn = $('#sb-run');
  if (!sqlEl || !out) return;
  const raw = (sqlEl.value || '').trim();
  if (!raw) { out.innerHTML = '<div class="card warn">введите SQL</div>'; return; }
  btn.disabled = true;
  out.innerHTML = '<div class="card">… выполняю на тестовой БД (read-only, timeout 5s) …</div>';
  // Отправляем SQL как есть — никаких обёрток. Хочешь EXPLAIN ANALYZE — напиши сам.
  const payload = { sql: raw, explain: false };
  try {
    const r = await fetch('/run-sql', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    if (!r.ok) {
      const e = await r.text();
      let detail = e;
      try { const j = JSON.parse(e); detail = j.detail || e; } catch (_) {}
      const cls = r.status === 400 ? 'warn' : 'err';
      const title = r.status === 400
        ? 'Запрос не разрешён в песочнице'
        : `Ошибка ${r.status}`;
      out.innerHTML = `<div class="card ${cls}">
        <div class="label">${title}</div>
        <pre style="white-space:pre-wrap;margin-top:6px">${esc(detail)}</pre>
      </div>`;
      return;
    }
    const d = await r.json();
    let planHtml = '';
    // если плана нет, но юзер сам обернул в EXPLAIN (… FORMAT JSON) — попробуем
    // распарсить JSON из первой ячейки и нарисовать дерево
    let parsedPlan = d.plan;
    if (!parsedPlan && d.rows?.length && d.columns?.length === 1) {
      try {
        const v = d.rows[0][0];
        const j = typeof v === 'string' ? JSON.parse(v) : v;
        if (Array.isArray(j) && j[0]?.Plan) parsedPlan = j[0];
      } catch (e) { /* не JSON-план — игнор */ }
    }
    if (parsedPlan) planHtml = renderPlan(parsedPlan);
    // авто-проброс Execution Time в поле отчёта (если карточка прогноза открыта)
    let autoFilled = false;
    if (parsedPlan && typeof parsedPlan['Execution Time'] === 'number') {
      const realEl = $('#pc-real-ms');
      const srcEl = $('#pc-source');
      const tog = $('#pc-help-tog');
      const reportBlock = $('#pc-report-block');
      if (realEl) {
        realEl.value = parsedPlan['Execution Time'].toFixed(3);
        if (srcEl) srcEl.value = 'explain_analyze';
        if (tog && !tog.checked) {                  // если «хочу помочь» выкл — включим
          tog.checked = true;
          if (reportBlock) reportBlock.style.display = '';
          if (tog.onchange) tog.onchange();
        }
        autoFilled = true;
      }
    }
    let resultHtml = '';
    if (!parsedPlan && d.columns?.length) {
      const headRow = '<tr>' + d.columns.map(c => `<th>${esc(c)}</th>`).join('') + '</tr>';
      const bodyRows = d.rows.map(r =>
        '<tr>' + r.map(c => `<td title="${esc(c)}">${esc(c)}</td>`).join('') + '</tr>'
      ).join('');
      const trunc = d.truncated ? ` <span class="warn">(показано ${d.row_count}, обрезано до 200)</span>` : '';
      resultHtml = `
        <div class="card">
          <div class="label">Результат</div>
          <div class="meta"><span>${d.row_count} строк${trunc}</span></div>
          <div class="rs-wrap"><table class="rs">${headRow}${bodyRows}</table></div>
        </div>`;
    }
    out.innerHTML = `
      <div class="card">
        <div class="meta">
          <span class="ok">✓ выполнено</span>
          <span>round-trip API: ${d.elapsed_ms.toFixed(0)}мс</span>
          ${autoFilled ? '<span class="ok">⤴ Execution Time подставлен в поле отчёта</span>' : (parsedPlan ? '<span class="ok">видишь Execution Time ниже? скопируй в отчёт.</span>' : '')}
        </div>
      </div>
      ${planHtml}
      ${resultHtml}`;
  } catch (e) {
    out.innerHTML = `<div class="card err">network: ${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
}
async function submitTimingReport() {
  const card = $('#pc-card');
  const btn = $('#pc-report-btn');
  const realStr = $('#pc-real-ms')?.value;
  const res = $('#pc-report-result');
  if (!realStr || !card) return;
  if (btn && btn.disabled) return;          // уже отправлен/в процессе — игнор
  const realMs = parseFloat(realStr);
  if (isNaN(realMs) || realMs < 0) {
    res.innerHTML = '<span class="err">введите число</span>';
    return;
  }
  const source = $('#pc-source')?.value || 'manual';
  if (btn) { btn.disabled = true; btn.textContent = '… отправляю …'; }
  res.innerHTML = '<span style="color:var(--mut)">… отправляю …</span>';
  try {
    const r = await fetch('/timing/report', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        sql: card.dataset.sql,
        real_ms: realMs,
        predicted_cost: parseFloat(card.dataset.cost || '0') || null,
        predicted_ms_lo: parseFloat(card.dataset.lo || '0') || null,
        predicted_ms_hi: parseFloat(card.dataset.hi || '0') || null,
        source,
        trace_id: card.dataset.trace || null,
      })
    });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      res.innerHTML = `<span class="err">не сохранено: ${esc(d.detail || d)}</span>`;
      if (btn) { btn.disabled = false; btn.textContent = 'Отправить отчёт'; }
      return;
    }
    if (d.diff_pct != null) {
      const sign = d.diff_pct >= 0 ? '+' : '';
      const cls = Math.abs(d.diff_pct) < 50 ? 'ok' : 'err';
      res.innerHTML = `<span class="pc-diff ${cls}">${sign}${d.diff_pct.toFixed(0)}% от прогноза</span>`;
    } else {
      res.innerHTML = '<span class="ok">✓ сохранено</span>';
    }
    if (btn) { btn.textContent = '✓ Отчёт отправлен'; }   // остаётся disabled до нового запроса
  } catch (e) {
    res.innerHTML = `<span class="err">network: ${esc(e.message)}</span>`;
    if (btn) { btn.disabled = false; btn.textContent = 'Отправить отчёт'; }
  }
}

// ── state диалога ──
let _task = '';                 // оригинальная NL-задача
let _history = [];              // массив ChatTurn'ов (assistant clarify + user content)
let _lastSQL = null;
let _lastApproved = false;
let _warningsShown = false;     // NL-warnings показываем ровно один раз на диалог
const msgs = $('#msgs');

function renderUser(text) {
  msgs.insertAdjacentHTML('beforeend',
    `<div class="msg user">${esc(text)}</div>`);
  msgs.scrollIntoView({behavior:'smooth', block:'end'});
}
function renderBot(html, cls='bot') {
  const div = document.createElement('div');
  div.className = 'msg ' + cls;
  div.innerHTML = html;
  msgs.appendChild(div);
  msgs.scrollIntoView({behavior:'smooth', block:'end'});
  return div;
}
function renderWarnings(warnings) {
  if (!warnings || !warnings.length) return;
  if (_warningsShown) return;        // уже видели в этом диалоге — не дублим
  _warningsShown = true;
  const html = warnings.map(w =>
    `<b>${esc(w.code)}</b> · ${esc(w.severity)}<br>${esc(w.message)}<br><small>${esc(w.hint)}</small>`
  ).join('<hr style="border:0;border-top:1px solid #6e4500;margin:8px 0">');
  renderBot('⚠ NL-валидатор предупреждает:<br>' + html, 'warn');
}
function resetDialog() {
  _task = ''; _history = []; _lastSQL = null; _lastApproved = false; _warningsShown = false;
  msgs.innerHTML = '';
  out.innerHTML = '';
  $('#task').value = '';
  $('#reset').style.display = 'none';
}
const _reset_btn = $('#reset');
if (_reset_btn) _reset_btn.onclick = resetDialog;

// Рендер "thinking"-потока (SSE-события из pipeline)
function appendThink(thinkEl, cls, text, time_s) {
  const t = time_s != null ? `<span class="t">${time_s.toFixed(1)}s</span>` : '';
  thinkEl.insertAdjacentHTML('beforeend',
    `<div class="step ${cls}">${text} ${t}</div>`);
  msgs.scrollIntoView({behavior:'smooth', block:'end'});
}

// Live-режим только когда нет clarify-истории (первый ход).
// SSE рисует поток мыслей, в конце даёт финальный SQL.
async function sendStream() {
  out.innerHTML = '';
  // bubble для thinking-стрима
  const bot = renderBot('<b>🧠 thinking…</b><div class="think" id="think-box"></div>', 'bot');
  const thinkEl = bot.querySelector('#think-box');
  const t0 = performance.now();
  let finalEv = null;

  try {
    const r = await fetch('/chat/stream', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({task: _task, history: []})
    });
    if (!r.ok || !r.body) {
      appendThink(thinkEl, 'err', `HTTP ${r.status}`);
      return;
    }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream:true});
      let nl;
      while ((nl = buf.indexOf('\\n\\n')) !== -1) {
        const chunk = buf.slice(0, nl);
        buf = buf.slice(nl + 2);
        if (!chunk.startsWith('data: ')) continue;
        const ev = JSON.parse(chunk.slice(6));
        const dt = (performance.now() - t0) / 1000;
        if (ev.event === 'nl_warnings') {
          renderWarnings(ev.warnings);
        } else if (ev.event === 'iter_start') {
          appendThink(thinkEl, 'iter', `── Итерация ${ev.iteration} ──`, dt);
        } else if (ev.event === 'generator_start') {
          const lessons = (ev.lessons && ev.lessons.length)
            ? ` (учтены уроки: ${ev.lessons.length})` : '';
          appendThink(thinkEl, 'gen', `🧮 генератор пишет SQL${lessons}…`, dt);
        } else if (ev.event === 'generator_done') {
          appendThink(thinkEl, 'gen', `✓ SQL готов <pre>${esc(ev.sql.slice(0,300))}</pre>`, dt);
        } else if (ev.event === 'non_sql_output') {
          appendThink(thinkEl, 'err',
            `🛑 модель ответила не SQL — нужно больше контекста, ранний выход<br>` +
            `<pre>${esc((ev.model_text || '').slice(0,400))}</pre>`, dt);
        } else if (ev.event === 'auditor_start') {
          appendThink(thinkEl, 'aud', `🛡 аудитор проверяет…`, dt);
        } else if (ev.event === 'auditor_done') {
          const v = ev.vulnerabilities || [];
          const ok = ev.approved ? '<span class="ok">approved</span>' : '<span class="err">rejected</span>';
          const vlist = v.length ? ' · ' + v.map(x => `${x.vuln_class}(${x.risk_score.toFixed(1)})`).join(', ') : '';
          appendThink(thinkEl, 'aud', `${ok} · риск ${ev.risk.toFixed(1)}${vlist}`, dt);
        } else if (ev.event === 'reflector_start') {
          appendThink(thinkEl, 'ref', `🧠 reflection пишет урок…`, dt);
        } else if (ev.event === 'reflector_done') {
          const ls = (ev.lessons || []).map(esc).join('<br>');
          appendThink(thinkEl, 'ref', `✓ урок: ${ls || '—'}`, dt);
        } else if (ev.event === 'final') {
          finalEv = ev;
        } else if (ev.event === 'error') {
          appendThink(thinkEl, 'err', `error: ${esc(ev.message)}`, dt);
        }
      }
    }
  } catch (e) {
    appendThink(thinkEl, 'err', `network error: ${esc(e.message)}`);
    return;
  }

  // Финал: показываем карточки SQL / vulns / audit_log
  if (!finalEv) return;
  _lastSQL = finalEv.final_sql;
  _lastApproved = finalEv.approved;
  const _nVulns = (finalEv.vulnerabilities || []).length;
  const verdict = !finalEv.approved
    ? '<span class="err">✗ rejected</span>'
    : _nVulns > 0
      ? `<span class="warn">⚠ approved с предупреждениями (${_nVulns})</span>`
      : '<span class="ok">✓ approved (чисто)</span>';
  const traj = (finalEv.risk_trajectory || []).map(x => x.toFixed(1)).join(' → ');
  const _pipeMs = (finalEv.pipeline_ms || 0).toFixed(0);
  const _iterMs = (finalEv.iteration_ms || []).map(x => x.toFixed(0)).join(' + ');
  const _iterMsHtml = _iterMs ? ` <small style="color:var(--mut)">(${_iterMs} мс по итерациям)</small>` : '';
  renderBot(`SQL готов · ${verdict} · итераций <b>${finalEv.iterations_used}</b>
             · риск <b>${traj}</b> · <b>${_pipeMs} мс</b>${_iterMsHtml}`);
  const vulnsHtml = (finalEv.vulnerabilities || []).map(v => `
    <div class="vuln ${v.risk_score < 4 ? 'low':''}">
      <b>${esc(v.vuln_class)}</b> · risk ${v.risk_score.toFixed(1)}<br>
      ${esc(v.description)}<br>
      <small class="ok">↳ ${esc(v.recommendation || '')}</small>
    </div>`).join('') || '<div class="ok">⚑ уязвимостей не найдено</div>';
  const runBtn = finalEv.approved
    ? ''
    : '<button class="ghost" disabled>SQL отклонён аудитором — выполнить нельзя</button>';
  const traceId = finalEv.trace_id;
  const traceLink = traceId
    ? `<a href="http://localhost:13001/trace/${traceId}" target="_blank">
         <button class="ghost">Открыть trace ${traceId.slice(0,8)} →</button></a>` : '';
  // Если SQL отклонён — Финальный SQL всё-таки нужен (карточки прогноза не будет).
  const rejectedSqlCard = finalEv.approved ? '' : `
    <div class="card">
      <div class="label">Финальный SQL (отклонён аудитором)</div>
      <pre>${esc(finalEv.final_sql)}</pre>
      <div class="row"><button class="ghost" disabled>SQL отклонён аудитором — выполнить нельзя</button> ${traceLink}</div>
    </div>`;
  out.innerHTML = `
    ${rejectedSqlCard}
    <div class="card">
      <div class="label">Уязвимости (последняя итерация)</div>
      ${vulnsHtml}
    </div>
    ${finalEv.approved ? renderPredictionCard(finalEv.final_sql, traceId) : ''}
    ${finalEv.approved ? renderSandboxCard(finalEv.final_sql) : ''}
    <div class="card">
      <div class="label">Audit log</div>
      <pre>${esc(finalEv.audit_log)}</pre>
    </div>
    <div id="run-out"></div>
    ${renderFeedback(finalEv)}`;
  if (traceId) {
    $('#lf-hint').innerHTML = `последний trace: <a href="http://localhost:13001/trace/${traceId}" target="_blank">${traceId.slice(0,8)}</a>`;
    $('#lf-hint').className = 'ok';
    const lf = $("#langfuse-frame"); if (lf) lf.src = `http://localhost:13001/trace/${traceId}`;
  }
  const runBtnEl = $('#run-sql');
  if (runBtnEl) runBtnEl.onclick = runApprovedSQL;
  if (finalEv.approved) { bindPredictionCard(finalEv.final_sql, traceId); bindSandboxCard(finalEv.final_sql); }
  bindFeedback(finalEv);
  $('#reset').style.display = '';
}

// ── отправить очередной ход в /chat ──
let _chatInFlight = false;          // защита от двойного клика «Начать»/опции
async function sendChat(answer /* optional — текстовый ответ юзера на clarify */) {
  if (_chatInFlight) return;        // игнорим дубль до завершения предыдущего
  _chatInFlight = true;
  if (answer) {
    _history.push({role:'user', content: answer});
    renderUser(answer);
  }
  out.innerHTML = '<div class="card">… запрос идёт …</div>';
  try {
    const r = await fetch('/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({task: _task, history: _history})
    });
    if (!r.ok) {
      out.innerHTML = `<div class="card err">HTTP ${r.status}: ${esc(await r.text())}</div>`;
      return;
    }
    const d = await r.json();
    if (d.nl_warnings && d.nl_warnings.length) renderWarnings(d.nl_warnings);

    if (d.type === 'clarify') {
      // assistant задал уточняющий вопрос → запоминаем в history и рисуем
      _history.push({role:'assistant', question: d.question, options: d.options || []});
      const opts = (d.options || []).map(o =>
        `<span class="opt" data-a="${esc(o)}">${esc(o)}</span>`).join('');
      const free = `<div class="answer-row">
                      <input type="text" placeholder="свой ответ…" id="free-answer">
                      <button id="free-send">→</button>
                    </div>`;
      renderBot(`<b>Уточнение:</b><br>${esc(d.question)}<div class="options">${opts}</div>${free}`,
                'bot clarify');
      out.innerHTML = '';
      // обработчики
      msgs.querySelectorAll('.opt').forEach(o => {
        o.onclick = () => sendChat(o.dataset.a);
      });
      const fa = $('#free-answer'), fb = $('#free-send');
      const submitFree = () => {
        const a = fa.value.trim();
        if (a) sendChat(a);
      };
      fa.onkeydown = e => { if (e.key === 'Enter') submitFree(); };
      fb.onclick = submitFree;
      return;
    }

    // d.type === 'sql' — финальный результат
    _lastSQL = d.final_sql;
    _lastApproved = d.approved;
    const _nVulnsChat = (d.vulnerabilities || []).length;
    const verdict = !d.approved
      ? '<span class="err">✗ rejected</span>'
      : _nVulnsChat > 0
        ? `<span class="warn">⚠ approved с предупреждениями (${_nVulnsChat})</span>`
        : '<span class="ok">✓ approved (чисто)</span>';
    const traj = (d.risk_trajectory || []).map(x => x.toFixed(1)).join(' → ');
    const _pMs = ((d.metadata && d.metadata.pipeline_ms) || 0).toFixed(0);
    const _iMs = ((d.metadata && d.metadata.iteration_ms) || []).map(x => x.toFixed(0)).join(' + ');
    const _iMsHtml = _iMs ? ` <small style="color:var(--mut)">(${_iMs} мс по итерациям)</small>` : '';
    renderBot(`SQL готов · ${verdict} · итераций <b>${d.iterations_used}</b>
               · риск <b>${traj}</b> · <b>${_pMs} мс</b>${_iMsHtml}`);

    const vulnsHtml = (d.vulnerabilities || []).map(v => `
      <div class="vuln ${v.risk_score < 4 ? 'low':''}">
        <b>${esc(v.vuln_class)}</b> · risk ${v.risk_score.toFixed(1)}<br>
        ${esc(v.description)}<br>
        <small class="ok">↳ ${esc(v.recommendation || '')}</small>
      </div>`).join('') || '<div class="ok">⚑ уязвимостей не найдено</div>';
    const runBtn = d.approved
      ? ''
      : '<button class="ghost" disabled>SQL отклонён аудитором — выполнить нельзя</button>';
    const traceId = d.trace_id;
    const traceLink = traceId
      ? `<a href="http://localhost:13001/trace/${traceId}" target="_blank">
           <button class="ghost">Открыть trace ${traceId.slice(0,8)} в Langfuse →</button></a>`
      : '';
    // SQL отклонён → показываем карточку с SQL, иначе SQL виден в «Команда для запуска»
    const rejectedSqlCard = d.approved ? '' : `
      <div class="card">
        <div class="label">Финальный SQL (отклонён аудитором)</div>
        <pre>${esc(d.final_sql)}</pre>
        <div class="row"><button class="ghost" disabled>SQL отклонён аудитором — выполнить нельзя</button> ${traceLink}</div>
      </div>`;
    out.innerHTML = `
      ${rejectedSqlCard}
      <div class="card">
        <div class="label">Уязвимости (последняя итерация)</div>
        ${vulnsHtml}
      </div>
      ${d.approved ? renderPredictionCard(d.final_sql, traceId) : ''}
      ${d.approved ? renderSandboxCard(d.final_sql) : ''}
      <div class="card">
        <div class="label">Audit log</div>
        <pre>${esc(d.audit_log)}</pre>
      </div>
      <div id="run-out"></div>
      ${renderFeedback(d)}`;
    if (traceId) {
      $('#lf-hint').innerHTML = `последний trace: <a href="http://localhost:13001/trace/${traceId}" target="_blank">${traceId.slice(0,8)}</a>`;
      $('#lf-hint').className = 'ok';
      const lf = $("#langfuse-frame"); if (lf) lf.src = `http://localhost:13001/trace/${traceId}`;
    }
    const runBtnEl = $('#run-sql');
    if (runBtnEl) runBtnEl.onclick = runApprovedSQL;
    if (d.approved) { bindPredictionCard(d.final_sql, traceId); bindSandboxCard(d.final_sql); }
    bindFeedback(d);
    $('#reset').style.display = '';
  } catch (e) {
    out.innerHTML = `<div class="card err">network error: ${esc(e.message)}</div>`;
  } finally {
    _chatInFlight = false;          // снимаем single-flight guard в любом случае
  }
}

// ── старт нового диалога: всегда Live (SSE) ──
const _go_btn = $('#go');
if (_go_btn) _go_btn.onclick = () => {
  const t = $('#task').value.trim();
  if (!t) return;
  resetDialog();
  _task = t;
  $('#task').value = t;
  renderUser(t);
  sendStream();
};

// (старая кнопка #go-stream удалена; хендлер ниже остаётся как no-op для совместимости)
const _stream_btn = $('#go-stream');
if (_stream_btn) _stream_btn.onclick = () => {
  const t = $('#task').value.trim();
  if (!t) return;
  resetDialog();
  _task = t;
  $('#task').value = t;
  renderUser(t);
  sendStream();
};

// ── Админка ──
function renderAdminContent(d) {
  const users = (d.users || []).slice(0, 20).map(u => `
    <tr>
      <td><b>${esc(u.name)}</b></td>
      <td>${u.requests}</td>
      <td><span class="ok">${u.approved}</span> / <span class="err">${u.rejected}</span></td>
      <td>${(u.top_tables || []).map(t => `${esc(t[0])} (${t[1]})`).join(', ') || '—'}</td>
      <td>${(u.top_vulns || []).map(v => `${esc(v[0])} (${v[1]})`).join(', ') || '—'}</td>
    </tr>
  `).join('');
  const tablesHtml = (d.top_tables || []).map(t => `
    <tr><td>${esc(t[0])}</td><td>${t[1]}</td></tr>`).join('');
  const vulnsHtml = (d.top_vulns || []).map(v => `
    <tr><td>${esc(v[0])}</td><td>${v[1]}</td></tr>`).join('');
  const lastHtml = (d.last_events || []).map(e => `
    <tr>
      <td><small>${esc(e.ts)}</small></td>
      <td><b>${esc(e.user || '?')}</b></td>
      <td>${esc(e.endpoint)}</td>
      <td><span class="ok">${e.approved === 'true' ? '✓' : e.approved === 'false' ? '✗' : ''}</span> ${esc((e.task||'').slice(0,60))}</td>
    </tr>`).join('');
  return `
    <div class="card stat-grid">
      <div><div class="stat-num">${d.total_events}</div><div class="stat-lbl">всего событий</div></div>
      <div><div class="stat-num ok">${d.approved}</div><div class="stat-lbl">approved</div></div>
      <div><div class="stat-num err">${d.rejected}</div><div class="stat-lbl">rejected</div></div>
      <div><div class="stat-num">${(d.users || []).length}</div><div class="stat-lbl">пользователей</div></div>
    </div>
    <div class="card">
      <div class="row" style="justify-content:space-between">
        <div class="label" style="margin:0">events.csv</div>
        <a href="/admin/export.csv" id="admin-dl" target="_blank">
          <button>⤓ Скачать CSV</button>
        </a>
      </div>
    </div>
    <div class="card">
      <div class="label">По пользователям</div>
      <table class="tt">
        <tr><th>user</th><th>запросов</th><th>approved/rejected</th><th>топ таблиц</th><th>топ vuln-классов</th></tr>
        ${users || '<tr><td colspan="5">пока пусто</td></tr>'}
      </table>
    </div>
    <div class="card stat-grid">
      <div>
        <div class="label">Топ таблиц</div>
        <table class="tt"><tr><th>table</th><th>обращений</th></tr>${tablesHtml || '<tr><td colspan="2">—</td></tr>'}</table>
      </div>
      <div>
        <div class="label">Топ vuln-классов</div>
        <table class="tt"><tr><th>class</th><th>находок</th></tr>${vulnsHtml || '<tr><td colspan="2">—</td></tr>'}</table>
      </div>
    </div>
    <div class="card">
      <div class="label">Последние 30 событий</div>
      <table class="tt">
        <tr><th>ts</th><th>user</th><th>endpoint</th><th>task</th></tr>
        ${lastHtml || '<tr><td colspan="4">—</td></tr>'}
      </table>
    </div>`;
}

async function adminLoadStats() {
  const r = await fetch('/admin/stats');
  if (r.status === 401) {
    sessionStorage.removeItem('sqlsec_admin_auth');
    _adminAuth = '';
    $('#admin-login-card').style.display = '';
    $('#admin-content').style.display = 'none';
    $('#admin-err').style.display = 'block';
    $('#admin-err').textContent = 'unauthorized — введите креды';
    return;
  }
  const d = await r.json();
  $('#admin-content').innerHTML = renderAdminContent(d);
  $('#admin-content').style.display = 'block';
  $('#admin-login-card').style.display = 'none';
  $('#admin-logout').style.display = '';
}

$('#admin-login').onclick = async () => {
  const u = $('#admin-user').value.trim();
  const p = $('#admin-pwd').value;
  if (!u || !p) return;
  _adminAuth = btoa(u + ':' + p);
  sessionStorage.setItem('sqlsec_admin_auth', _adminAuth);
  $('#admin-err').style.display = 'none';
  await adminLoadStats();
};
$('#admin-logout').onclick = () => {
  sessionStorage.removeItem('sqlsec_admin_auth');
  _adminAuth = '';
  $('#admin-content').style.display = 'none';
  $('#admin-login-card').style.display = '';
  $('#admin-logout').style.display = 'none';
};

// При клике на таб «Админка» — попытка автозагрузки если уже залогинены
document.querySelectorAll('.tab').forEach(t => {
  if (t.dataset.pane === 'admin') {
    t.addEventListener('click', () => {
      if (_adminAuth) adminLoadStats();
    });
  }
});

// ── feedback (👍/👎 + комментарий) ──
function renderFeedback(d) {
  return `
    <div class="card" id="fb-card">
      <div class="label">Оцените результат</div>
      <div class="row" style="margin-top:8px">
        <button class="fb-btn up"   data-rating="up">👍 Сработал</button>
        <button class="fb-btn down" data-rating="down">👎 Не сработал</button>
      </div>
      <textarea class="fb-comment" id="fb-comment"
                placeholder="опц.: что не так / что улучшить (для дообучения)"></textarea>
      <div class="row" style="margin-top:8px">
        <button id="fb-send" disabled>Отправить отзыв</button>
        <small style="color:var(--mut)">данные пишутся в data/feedback.jsonl + Langfuse score</small>
      </div>
    </div>`;
}

function bindFeedback(d) {
  const card = $('#fb-card');
  if (!card) return;
  let chosen = null;
  card.querySelectorAll('.fb-btn').forEach(b => {
    b.onclick = () => {
      card.querySelectorAll('.fb-btn').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      chosen = b.dataset.rating;
      $('#fb-send').disabled = false;
    };
  });
  $('#fb-send').onclick = async () => {
    if (!chosen) return;
    const btn = $('#fb-send');
    btn.disabled = true;
    btn.textContent = '…';
    try {
      const r = await fetch('/feedback', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          task: _task,
          final_sql: d.final_sql,
          rating: chosen,
          comment: $('#fb-comment').value.trim() || null,
          trace_id: d.trace_id || null,
          iterations_used: d.iterations_used,
          approved: d.approved,
        })
      });
      const j = await r.json();
      const langSync = j.langfuse_synced ? ' (+ Langfuse score)' : '';
      card.innerHTML = `<div class="fb-thanks">✓ спасибо за отзыв${langSync}</div>`;
    } catch (e) {
      btn.disabled = false; btn.textContent = 'Отправить отзыв';
      card.insertAdjacentHTML('beforeend',
        `<div class="err" style="margin-top:8px">network error: ${esc(e.message)}</div>`);
    }
  };
}

async function runApprovedSQL() {
  if (!_lastSQL || !_lastApproved) return;
  const runOut = $('#run-out');
  const btn = $('#run-sql');
  const tog = document.querySelector('.explain-tog');
  const explain = !!tog?.checked;
  localStorage.setItem('explain', explain ? '1' : '');
  btn.disabled = true;
  runOut.innerHTML = `<div class="card">… ${explain ? 'EXPLAIN ANALYZE на demo_db' : 'выполняю на demo_db'} (read-only, timeout 5s) …</div>`;
  try {
    const r = await fetch('/run-sql', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sql: _lastSQL, explain})
    });
    if (!r.ok) {
      const err = await r.text();
      runOut.innerHTML = `<div class="card err">HTTP ${r.status}: ${esc(err)}</div>`;
      return;
    }
    const d = await r.json();
    const planHtml = renderPlan(d.plan);
    // если был EXPLAIN — таблица результатов пустая, не рендерим её
    let resultHtml = '';
    if (!d.plan) {
      const headRow = '<tr>' + d.columns.map(c => `<th>${esc(c)}</th>`).join('') + '</tr>';
      const bodyRows = d.rows.map(r =>
        '<tr>' + r.map(c => `<td title="${esc(c)}">${esc(c)}</td>`).join('') + '</tr>'
      ).join('');
      const trunc = d.truncated ? ` <span class="warn">(показано ${d.row_count}, обрезано до 200)</span>` : '';
      resultHtml = `
        <div class="card">
          <div class="label">Результат</div>
          <div class="meta">
            <span>${d.row_count} строк${trunc}</span>
          </div>
          <div class="rs-wrap"><table class="rs">${headRow}${bodyRows}</table></div>
        </div>`;
    }
    runOut.innerHTML = `
      <div class="card">
        <div class="meta">
          <span class="ok">✓ ${d.plan ? 'EXPLAIN ANALYZE выполнен' : 'выполнено'}</span>
          <span>round-trip API: ${d.elapsed_ms.toFixed(0)}мс</span>
        </div>
      </div>
      ${planHtml}
      ${resultHtml}`;
  } catch (e) {
    runOut.innerHTML = `<div class="card err">network error: ${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
}
</script>
</body></html>
"""

# подставляем сгенерированные карточки уязвимостей в шаблон
_UI_HTML = _UI_HTML.replace("<!-- VULN_CARDS -->", _render_vuln_pane())


@app.get("/", response_class=HTMLResponse)
def ui() -> str:
    """@brief Минимальный Web-UI: поле ввода NL → /audit → подсветка результата."""
    return _UI_HTML


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """@brief Liveness-проба для compose/k8s."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics_text() -> Any:
    """@brief Prometheus exposition (дубль для удобства — основной канал :9100)."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(m.app_metrics.render(),
                             media_type="text/plain; version=0.0.4")


@app.post("/audit", response_model=AuditResponse)
def audit(req: AuditRequest, user: str = Depends(get_user)) -> AuditResponse:
    """
    @brief Главный endpoint: NL-задача → (SQL + audit_log).
    @details
        Артефакт системы по ТЗ — НЕ исполнение SQL, а сам SQL и аудит-лог.
        Прогон через run_instrumented: метрики и трейсы пишутся автоматически.
    """
    try:
        res = run_instrumented(
            req.task,
            max_iterations=req.max_iterations,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pipeline error: {e}")

    # последний аудит = из последней итерации (там итоговые вердикты)
    last_audit = res.iterations_log[-1].audit_result if res.iterations_log else None
    vulns = [VulnOut(vuln_class=v.vuln_class, risk_score=v.risk_score,
                     description=v.description, recommendation=v.recommendation)
             for v in (last_audit.vulnerabilities if last_audit else [])]

    ev.log_event(
        user=user, endpoint="/audit", task=req.task, sql=res.final_sql,
        approved=res.approved, iterations=res.iterations_used,
        vuln_classes=[v.vuln_class for v in vulns],
        trace_id=res.metadata.get("trace_id"),
    )
    return AuditResponse(
        final_sql=res.final_sql,
        approved=res.approved,
        iterations_used=res.iterations_used,
        risk_trajectory=res.metadata.get("risk_trajectory", []),
        vulnerabilities=vulns,
        audit_log=res.audit_log,
        metadata=res.metadata,
    )


# ─── /audit-sql: «аудит готового SQL» (минуя генератор) ─────────────────────
# Используется кнопкой «Аудит этого SQL» в каталоге уязвимостей:
# жюри жмёт, видит ровно тот SQL из примера прогнанным через Phase 1+2.
# Не итеративный, без reflection — одна итерация, один аудит, готово.
class AuditSqlRequest(BaseModel):
    sql: str = Field(..., min_length=3, max_length=10000)
    label: str | None = None       # опц. подпись (имя класса из каталога)


@app.post("/audit-sql", response_model=AuditResponse)
def audit_sql(req: AuditSqlRequest, user: str = Depends(get_user)) -> AuditResponse:
    """@brief Прогоняет переданный SQL через аудитор (без генерации)."""
    import time as _time
    from case3.contracts import IterationLog
    from case3.nodes.auditor import HybridAuditor

    t0 = _time.perf_counter()
    try:
        auditor = HybridAuditor()
        audit = auditor.audit(req.sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"auditor error: {e}")
    dt_ms = round((_time.perf_counter() - t0) * 1000.0, 2)

    vulns = [VulnOut(vuln_class=v.vuln_class, risk_score=v.risk_score,
                     description=v.description, recommendation=v.recommendation)
             for v in audit.vulnerabilities]
    # Лог в формате, похожем на pipeline._render_log
    vuln_block = "\n".join(
        f"  ⚠ {v.vuln_class} ({v.risk_score:.1f}): {v.description}"
        for v in audit.vulnerabilities
    ) or "  (уязвимостей не найдено)"
    audit_log = (
        f"=== AUDIT LOG (только аудит, без генератора) ===\n\n"
        f"--- Итерация 1 ---\n"
        f"SQL: {req.sql}\n"
        f"Риск: {audit.overall_risk_score:.1f}  Одобрено: {audit.approved}\n"
        f"{vuln_block}\n"
        f"Вердикт: {audit.summary}"
    )
    label = req.label or "audit-sql"
    ev.log_event(
        user=user, endpoint="/audit-sql", task=label, sql=req.sql,
        approved=audit.approved, iterations=1,
        vuln_classes=[v.vuln_class for v in vulns],
    )
    return AuditResponse(
        final_sql=req.sql,
        approved=audit.approved,
        iterations_used=1,
        risk_trajectory=[audit.overall_risk_score],
        vulnerabilities=vulns,
        audit_log=audit_log,
        metadata={
            "pipeline_ms": dt_ms,
            "iteration_ms": [],
            "audit_only": True,
            "source_label": label,
        },
    )


# Stateless: UI шлёт всю историю каждый раз. Сервер либо возвращает clarify
# (question + options), либо запускает полный pipeline (run_instrumented).
# До MAX_CLARIFY_ROUNDS=2 уточнений; на третьем — force_sql.
MAX_CLARIFY_ROUNDS = 2


class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str | None = None          # для user.content или assistant.sql
    question: str | None = None         # assistant.clarify
    options: list[str] | None = None    # assistant.clarify


class ChatRequest(BaseModel):
    task: str = Field(..., min_length=3, max_length=2000,
                      description="Оригинальная NL-задача (первое сообщение)")
    history: list[ChatTurn] = Field(default_factory=list,
                                    description="Раунды clarify, если уже были")


class NLWarningOut(BaseModel):
    code: str
    severity: str
    message: str
    hint: str = ""


class ChatResponse(BaseModel):
    type: str = Field(..., pattern="^(clarify|sql)$")
    # для type=clarify:
    question: str | None = None
    options: list[str] | None = None
    # для type=sql:
    final_sql: str | None = None
    approved: bool | None = None
    iterations_used: int | None = None
    risk_trajectory: list[float] | None = None
    vulnerabilities: list[VulnOut] | None = None
    audit_log: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] | None = None
    # NL-warnings (информационные, не блокирующие)
    nl_warnings: list[NLWarningOut] = Field(default_factory=list)


_CLARIF_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "data", "clarifications.jsonl")


def _persist_clarification(task: str, history: list[ChatTurn],
                           final_sql: str | None, approved: bool | None) -> None:
    """@brief Запись в data/clarifications.jsonl — для будущего few-shot/RLHF.
    Никакой PII (текст пользователя) фильтровать не пытаемся: это локальная
    разработка, в проде поверх — anon-pipeline."""
    import datetime
    import logging
    import uuid
    try:
        os.makedirs(os.path.dirname(_CLARIF_LOG), exist_ok=True)
        with open(_CLARIF_LOG, "a", encoding="utf-8") as f:
            f.write(_json.dumps({
                "id": uuid.uuid4().hex[:12],
                "ts": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "task": task,
                "history": [h.model_dump(exclude_none=True) for h in history],
                "final_sql": final_sql,
                "approved": approved,
            }, ensure_ascii=False) + "\n")
    except Exception as e:
        # Не валим запрос пользователя, но фиксируем в логах — нам важно
        # видеть когда persist ломается (это собирает датасет для будущего fine-tune).
        logging.getLogger("uvicorn.error").warning("clarif persist failed: %r", e)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: str = Depends(get_user)) -> ChatResponse:
    """@brief Multi-turn с clarification. Stateless (history от UI каждый раз)."""
    # 1) NL-валидация — только на первом ходу (history пустой)
    nl_warnings: list[NLWarningOut] = []
    if not req.history:
        try:
            from case3.audit.nl_validator import validate_nl
            for w in validate_nl(req.task):
                nl_warnings.append(NLWarningOut(
                    code=w.code, severity=w.severity,
                    message=w.message, hint=w.hint))
        except Exception:
            pass

    # 2) Подсчёт уже состоявшихся раундов clarify
    n_clarifies = sum(1 for h in req.history if h.role == "assistant" and h.question)
    force_sql = n_clarifies >= MAX_CLARIFY_ROUNDS

    # 3) LLM генератор — спрашиваем либо clarify, либо SQL
    try:
        from case3.llm.factory import make_llm
        from case3.schema.linker import SchemaLinker
        from case3.nodes.generator import LLMGenerator
        llm = make_llm()
        db_schema = SchemaLinker().link_text(req.task, k=4, max_cols=12, fk_closure=False)
        gen = LLMGenerator(llm=llm, db_schema=db_schema)
        # переведём history в формат, который понимает generate_or_clarify
        clar_hist = [
            {"role": h.role,
             "question": h.question or "",
             "options": h.options or [],
             "content": h.content or ""}
            for h in req.history
        ]
        out = gen.generate_or_clarify(req.task, clarify_history=clar_hist,
                                      force_sql=force_sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generator error: {e}")

    # 4) Если clarify — возвращаем сразу, pipeline не запускаем
    if out.get("type") == "clarify":
        return ChatResponse(type="clarify",
                            question=out.get("question"),
                            options=out.get("options") or [],
                            nl_warnings=nl_warnings)

    # 5) Иначе — собираем «расширенную» задачу для pipeline (NL + ответы пользователя)
    final_task = req.task
    for h in req.history:
        if h.role == "user" and h.content:
            final_task += f"\nУточнение: {h.content}"

    # 6) Полный пайплайн (тот же что для /audit) — на расширенной задаче
    try:
        res = run_instrumented(final_task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pipeline error: {e}")

    last_audit = res.iterations_log[-1].audit_result if res.iterations_log else None
    vulns = [VulnOut(vuln_class=v.vuln_class, risk_score=v.risk_score,
                     description=v.description, recommendation=v.recommendation)
             for v in (last_audit.vulnerabilities if last_audit else [])]

    # 7) Сохраним диалог в jsonl — это будущий positive few-shot
    if req.history:
        _persist_clarification(req.task, req.history, res.final_sql, res.approved)

    ev.log_event(
        user=user, endpoint="/chat", task=req.task, sql=res.final_sql,
        approved=res.approved, iterations=res.iterations_used,
        vuln_classes=[v.vuln_class for v in vulns],
        trace_id=res.metadata.get("trace_id"),
    )
    return ChatResponse(
        type="sql",
        final_sql=res.final_sql,
        approved=res.approved,
        iterations_used=res.iterations_used,
        risk_trajectory=res.metadata.get("risk_trajectory", []),
        vulnerabilities=vulns,
        audit_log=res.audit_log,
        trace_id=res.metadata.get("trace_id"),
        metadata=res.metadata,
        nl_warnings=nl_warnings,
    )


# ─── /chat/stream: SSE-стрим этапов пайплайна (live thinking) ───────────────
# Возвращает text/event-stream. UI парсит через fetch+ReadableStream.
# Каждое событие — JSON-объект с полем "event": iter_start / generator_start /
# generator_done / auditor_done / reflector_done / final.
#
# Pipeline.run() — синхронный (тяжёлые LLM-вызовы). Запускаем его в
# threadpool через run_in_executor, шлём события через asyncio.Queue,
# event loop FastAPI не блокируется и SSE-чанки уходят в браузер по мере
# появления.
@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, user: str = Depends(get_user)):
    """@brief SSE-стрим этапов pipeline'а — для 'thinking' UI."""
    import asyncio

    # NL-валидация — первым событием
    nl_warnings: list[dict] = []
    try:
        from case3.audit.nl_validator import validate_nl
        for w in validate_nl(req.task):
            nl_warnings.append({
                "code": w.code, "severity": w.severity,
                "message": w.message, "hint": w.hint
            })
    except Exception:
        pass

    # Расширим task ответами пользователя из history
    final_task = req.task
    for h in req.history:
        if h.role == "user" and h.content:
            final_task += f"\nУточнение: {h.content}"

    loop = asyncio.get_running_loop()
    q: "asyncio.Queue[dict]" = asyncio.Queue()
    SENTINEL = object()

    def emit_threadsafe(event: dict) -> None:
        # вызывается из worker-потока pipeline; шлём в event-loop коректно
        loop.call_soon_threadsafe(q.put_nowait, event)

    def worker_blocking() -> None:
        try:
            res = run_instrumented(final_task, on_event=emit_threadsafe)
            last_audit = res.iterations_log[-1].audit_result if res.iterations_log else None
            vcs = [v.vuln_class for v in (last_audit.vulnerabilities if last_audit else [])]
            ev.log_event(
                user=user, endpoint="/chat/stream", task=req.task,
                sql=res.final_sql, approved=res.approved,
                iterations=res.iterations_used, vuln_classes=vcs,
                trace_id=res.metadata.get("trace_id"),
            )
            emit_threadsafe({
                "event": "final",
                "approved": res.approved,
                "iterations_used": res.iterations_used,
                "risk_trajectory": res.metadata.get("risk_trajectory", []),
                "pipeline_ms": res.metadata.get("pipeline_ms"),
                "iteration_ms": res.metadata.get("iteration_ms", []),
                "final_sql": res.final_sql,
                "audit_log": res.audit_log,
                "trace_id": res.metadata.get("trace_id"),
                "vulnerabilities": [
                    {"vuln_class": v.vuln_class, "risk_score": v.risk_score,
                     "description": v.description,
                     "recommendation": v.recommendation}
                    for v in (last_audit.vulnerabilities if last_audit else [])
                ],
            })
        except Exception as e:
            emit_threadsafe({"event": "error", "message": str(e)})
        finally:
            loop.call_soon_threadsafe(q.put_nowait, SENTINEL)

    async def stream():
        # NL-warnings первыми
        if nl_warnings:
            yield "data: " + _json.dumps(
                {"event": "nl_warnings", "warnings": nl_warnings},
                ensure_ascii=False) + "\n\n"
        # запускаем pipeline в threadpool
        loop.run_in_executor(None, worker_blocking)
        while True:
            ev = await q.get()
            if ev is SENTINEL:
                break
            yield "data: " + _json.dumps(ev, ensure_ascii=False) + "\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


# ─── /feedback: оценка финального SQL — RLHF-датасет + Langfuse score ──────
# Складывается в data/feedback.jsonl. Если есть LANGFUSE_PUBLIC_KEY и trace_id —
# параллельно посылается score в Langfuse (filterable в UI: thumbs_up / down).
_FEEDBACK_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "data", "feedback.jsonl")


class FeedbackRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=2000)
    final_sql: str | None = None
    rating: str = Field(..., pattern="^(up|down)$",
                        description="up = сработал, down = не сработал")
    comment: str | None = Field(None, max_length=1000)
    trace_id: str | None = None
    iterations_used: int | None = None
    approved: bool | None = None


class FeedbackResponse(BaseModel):
    ok: bool
    langfuse_synced: bool


def _persist_feedback(req: FeedbackRequest) -> None:
    """@brief Запись в data/feedback.jsonl — RLHF/eval-данные."""
    import datetime
    import logging
    import uuid
    try:
        os.makedirs(os.path.dirname(_FEEDBACK_LOG), exist_ok=True)
        with open(_FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(_json.dumps({
                "id": uuid.uuid4().hex[:12],
                "ts": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                **req.model_dump(exclude_none=True),
            }, ensure_ascii=False) + "\n")
    except Exception as e:
        logging.getLogger("uvicorn.error").warning("feedback persist failed: %r", e)


def _sync_langfuse_score(req: FeedbackRequest) -> bool:
    """@brief Послать score в Langfuse (если ключи есть и trace_id известен)."""
    if not req.trace_id:
        return False
    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        return False
    try:
        from langfuse import Langfuse
        lf = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ.get("LANGFUSE_HOST", "http://langfuse:3000"),
        )
        # score: 1.0 = сработал, 0.0 = не сработал
        lf.score(trace_id=req.trace_id,
                 name="user_thumbs",
                 value=1.0 if req.rating == "up" else 0.0,
                 comment=req.comment or "")
        lf.flush()
        return True
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").warning(
            "langfuse score sync failed: %r", e)
        return False


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(req: FeedbackRequest, user: str = Depends(get_user)) -> FeedbackResponse:
    """@brief Оценка финального SQL пользователем (для RLHF/обучения и Langfuse UI)."""
    _persist_feedback(req)
    synced = _sync_langfuse_score(req)
    ev.log_event(
        user=user, endpoint="/feedback", task=req.task, sql=req.final_sql or "",
        approved=req.approved, iterations=req.iterations_used,
        rating=req.rating, comment=req.comment,
        trace_id=req.trace_id,
    )
    return FeedbackResponse(ok=True, langfuse_synced=synced)


# ─── /run-sql: исполнить approved SQL на demo_db ────────────────────────────
# Для демо. На проде артефактом остаётся SQL, не выполнение — этот endpoint
# нужен только чтобы жюри увидело результат в UI. Защита: только SELECT/WITH,
# statement_timeout 5 сек, LIMIT 200 принудительно.
class RunSQLRequest(BaseModel):
    sql: str = Field(..., min_length=5, max_length=5000)
    explain: bool = False     # EXPLAIN (ANALYZE) — per-op тайминг вместо результата


class RunSQLResponse(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    elapsed_ms: float
    plan: dict | None = None  # EXPLAIN (FORMAT JSON) если запрошен


_RUN_SQL_MAX_ROWS = 200


def _is_safe_select(sql: str) -> bool:
    """
    @brief Допускаем только SELECT / WITH, в т.ч. внутри EXPLAIN (…) / EXPLAIN ANALYZE.
    @details EXPLAIN ANALYZE исполняет вложенный запрос — отсекаем «EXPLAIN DELETE FROM …».
    """
    s = sql.strip().rstrip(";").lstrip()
    # снимем ведущие комментарии
    while s.startswith("--") or s.startswith("/*"):
        if s.startswith("--"):
            nl = s.find("\n")
            s = s[nl + 1:].lstrip() if nl != -1 else ""
        else:
            cl = s.find("*/")
            s = s[cl + 2:].lstrip() if cl != -1 else ""
    # снимем EXPLAIN-обёртку (и опциональные скобочные опции после EXPLAIN)
    if s.lower().startswith("explain"):
        s = s[len("explain"):].lstrip()
        if s.startswith("("):
            paren = 0
            for i, c in enumerate(s):
                if c == "(":
                    paren += 1
                elif c == ")":
                    paren -= 1
                    if paren == 0:
                        s = s[i + 1:].lstrip()
                        break
        # после EXPLAIN могут идти слова ANALYZE/VERBOSE без скобок
        while s.lower().startswith(("analyze", "verbose", "buffers", "costs", "timing", "summary", "format")):
            # сожрём слово (и опц. JSON/TEXT после FORMAT)
            sp = s.find(" ")
            if sp == -1:
                s = ""
                break
            s = s[sp + 1:].lstrip()
    head = s[:6].lower()
    return head.startswith("select") or head.startswith("with ")


@app.post("/run-sql", response_model=RunSQLResponse)
def run_sql(req: RunSQLRequest, user: str = Depends(get_user)) -> RunSQLResponse:
    """@brief Выполнить SQL на demo_db (только read-only)."""
    import time
    if not _is_safe_select(req.sql):
        raise HTTPException(
            status_code=400,
            detail=(
                "В песочнице разрешены только SELECT / WITH (в т.ч. под EXPLAIN). "
                "DML/DDL (DELETE / UPDATE / INSERT / DROP / TRUNCATE / GRANT / ALTER) "
                "не исполняем: EXPLAIN ANALYZE на них реально модифицирует данные demo_db.\n"
                "\n"
                "Что сделать вместо:\n"
                " • для оценки плана (без исполнения) — обычный EXPLAIN без ANALYZE:\n"
                "       EXPLAIN (FORMAT JSON) DELETE FROM ... WHERE ...;\n"
                " • для реального времени — SELECT-прокси с тем же WHERE:\n"
                "       EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)\n"
                "       SELECT count(*) FROM ... WHERE ...;\n"
                "   (получишь Execution Time сканирования по тем же строкам, "
                "сам DELETE добавит ~write-overhead).\n"
            ),
        )
    try:
        import psycopg2
    except ImportError:
        raise HTTPException(status_code=500, detail="psycopg2 не доступен в контейнере")

    cfg = dict(
        host=os.environ.get("DB_HOST", "db"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "demo_db"),
        user=os.environ.get("DB_USER", "distr_user"),
        password=os.environ.get("DB_PASSWORD", "pass"),
        connect_timeout=5,
    )
    t0 = time.perf_counter()
    try:
        conn = psycopg2.connect(**cfg)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("SET LOCAL statement_timeout = '5s'")
        cur.execute("SET LOCAL default_transaction_read_only = on")
        if req.explain:
            # EXPLAIN ANALYZE исполняет запрос → даёт реальное время и per-op разбивку.
            # Для SELECT в read-only транзакции это безопасно (rollback всё равно).
            cur.execute("EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON, COSTS, TIMING) " + req.sql)
            plan_raw = cur.fetchone()[0]          # list[{Plan, Execution Time, ...}]
            plan = plan_raw[0] if isinstance(plan_raw, list) and plan_raw else plan_raw
            cols, rows, truncated = [], [], False
        else:
            cur.execute(req.sql)
            cols = [d.name for d in cur.description] if cur.description else []
            # ограничим вывод
            rows = cur.fetchmany(_RUN_SQL_MAX_ROWS + 1)
            truncated = len(rows) > _RUN_SQL_MAX_ROWS
            rows = rows[:_RUN_SQL_MAX_ROWS]
            plan = None
        conn.rollback()
        conn.close()
    except psycopg2.Error as e:
        # rollback на всякий + понятная ошибка
        try:
            conn.rollback(); conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"DB error: {e.pgerror or str(e)}")

    # сериализация значений для JSON: dates/decimals → str, JSON-планы (list/dict) — как есть
    def cell(v):
        if v is None or isinstance(v, (int, float, str, bool, list, dict)):
            return v
        return str(v)
    out_rows = [[cell(c) for c in r] for r in rows]
    ev.log_event(user=user, endpoint="/run-sql", task="", sql=req.sql,
                 approved=True, iterations=None)
    return RunSQLResponse(
        columns=cols,
        rows=out_rows,
        row_count=len(out_rows),
        truncated=truncated,
        elapsed_ms=(time.perf_counter() - t0) * 1000,
        plan=plan,
    )


# ─── /predict-time + /timing/report: аналитический прогноз и обратная связь ─
# Идея: исполнять SQL на проде заказчика МЫ не имеем права (ТЗ). Поэтому:
#   1) /predict-time — делаем безопасный EXPLAIN (БЕЗ ANALYZE) на demo_db.
#      Получаем cost, структуру плана и подсказки. Это «аналитический прогноз».
#   2) Юзеру выдаём SQL-обёртки (EXPLAIN ANALYZE, pg_stat_statements), которые
#      он сам запускает на СВОЕЙ боевой БД и получает реальное время.
#   3) /timing/report — юзер присылает реальное время; пишем пары
#      (cost, real_ms) в data/timing.jsonl. По расхождению видно:
#        · большое расхождение → плохой план/архитектура БД заказчика,
#        · систематическая ошибка → нашему агенту нужна калибровка.
class PredictTimeRequest(BaseModel):
    sql: str = Field(..., min_length=5, max_length=10000)


class PredictTimeResponse(BaseModel):
    cost: float
    rows_estimate: int
    plan_summary: str
    plan_tree: list[dict]
    hints: list[str]
    predicted_ms_lo: float
    predicted_ms_hi: float
    note: str
    error: str | None = None


def _walk_plan(node: dict, depth: int = 0) -> list[dict]:
    """@brief Линеаризует план в плоский список для UI-рендера."""
    out = [{
        "depth": depth,
        "node_type": node.get("Node Type", "?"),
        "relation": node.get("Relation Name"),
        "cost": float(node.get("Total Cost", 0.0)),
        "rows": int(node.get("Plan Rows", 0)),
    }]
    for c in node.get("Plans", []) or []:
        out.extend(_walk_plan(c, depth + 1))
    return out


def _collect_hints(root: dict) -> list[str]:
    """@brief Архитектурные подсказки: что в плане потенциально болит на проде."""
    hints: list[str] = []
    def walk(n: dict, parent_rows: int = 0) -> None:
        nt = n.get("Node Type", "")
        rel = n.get("Relation Name")
        rows = int(n.get("Plan Rows", 0))
        if "Seq Scan" in nt and rel:
            hints.append(
                f"Seq Scan на «{rel}» — на проде с миллионами строк это медленно. "
                f"Индекс по WHERE-колонкам уберёт scan."
            )
        if nt == "Nested Loop":
            children = n.get("Plans", []) or []
            if children and int(children[0].get("Plan Rows", 0)) > 1000:
                hints.append(
                    "Nested Loop с большим внешним набором — на проде станет квадратичным. "
                    "Hash/Merge Join + индекс на ключе соединения."
                )
        if "Sort" in nt and rows > 10000:
            hints.append(
                "Sort на большом объёме — индекс с нужным порядком уберёт сортировку."
            )
        for c in n.get("Plans", []) or []:
            walk(c, rows)
    walk(root)
    return hints[:5]


@app.post("/predict-time", response_model=PredictTimeResponse)
def predict_time(req: PredictTimeRequest, user: str = Depends(get_user)) -> PredictTimeResponse:
    """
    @brief EXPLAIN (FORMAT JSON, БЕЗ ANALYZE) на demo_db — безопасно, не исполняет.
    @details Cost даёт оценку «по структуре плана», без знания реальных объёмов
             заказчика. На проде масштабируется с размером данных — калибровка
             через /timing/report.
    """
    if not _is_safe_select(req.sql):
        return PredictTimeResponse(
            cost=0.0, rows_estimate=0, plan_summary="", plan_tree=[], hints=[],
            predicted_ms_lo=0.0, predicted_ms_hi=0.0,
            note="не SELECT/WITH — анализ не делаем",
            error="EXPLAIN доступен только для SELECT/WITH",
        )
    try:
        import psycopg2
    except ImportError:
        return PredictTimeResponse(
            cost=0.0, rows_estimate=0, plan_summary="", plan_tree=[], hints=[],
            predicted_ms_lo=0.0, predicted_ms_hi=0.0,
            note="psycopg2 не доступен в контейнере", error="no psycopg2")
    cfg = dict(
        host=os.environ.get("DB_HOST", "db"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "demo_db"),
        user=os.environ.get("DB_USER", "distr_user"),
        password=os.environ.get("DB_PASSWORD", "pass"),
        connect_timeout=5,
    )
    try:
        conn = psycopg2.connect(**cfg)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("SET LOCAL statement_timeout = '5s'")
        cur.execute("SET LOCAL default_transaction_read_only = on")
        cur.execute("EXPLAIN (FORMAT JSON, COSTS) " + req.sql)
        plan_raw = cur.fetchone()[0]
        conn.rollback(); conn.close()
    except Exception as e:
        return PredictTimeResponse(
            cost=0.0, rows_estimate=0, plan_summary="", plan_tree=[], hints=[],
            predicted_ms_lo=0.0, predicted_ms_hi=0.0,
            note="EXPLAIN не удался — синтаксис SQL или таблиц нет на demo_db",
            error=str(e)[:200],
        )
    plan = plan_raw[0] if isinstance(plan_raw, list) and plan_raw else plan_raw
    root = plan.get("Plan", {})
    cost = float(root.get("Total Cost", 0.0))
    rows = int(root.get("Plan Rows", 0))
    summary = root.get("Node Type", "?")
    if rel := root.get("Relation Name"):
        summary += f" on {rel}"
    hints = _collect_hints(root)
    # широкий диапазон без калибровки (cold cache 0.5 мс/cost, hot 0.01)
    return PredictTimeResponse(
        cost=cost, rows_estimate=rows,
        plan_summary=summary,
        plan_tree=_walk_plan(root),
        hints=hints,
        predicted_ms_lo=cost * 0.01,
        predicted_ms_hi=cost * 0.5,
        note="оценка на demo_db (60 таблиц faker); на prod масштабируется с объёмом — нужны отчёты юзеров для калибровки",
    )


_TIMING_LOG = "data/timing.jsonl"


class TimingReportRequest(BaseModel):
    sql: str = Field(..., max_length=10000)
    real_ms: float = Field(..., ge=0, le=600_000)
    predicted_cost: float | None = None
    predicted_ms_lo: float | None = None
    predicted_ms_hi: float | None = None
    source: str = "manual"     # manual / explain_analyze / pg_stat_statements
    comment: str = ""
    trace_id: str | None = None


class TimingReportResponse(BaseModel):
    ok: bool
    diff_pct: float | None = None   # (real − mid_prediction) / mid_prediction × 100


@app.post("/timing/report", response_model=TimingReportResponse)
def timing_report(req: TimingReportRequest, user: str = Depends(get_user)) -> TimingReportResponse:
    """@brief Юзер прислал реальное время с его боевой БД — пишем в jsonl."""
    from datetime import datetime as _dt
    import threading as _th
    diff_pct: float | None = None
    if req.predicted_ms_lo is not None and req.predicted_ms_hi is not None:
        mid = (req.predicted_ms_lo + req.predicted_ms_hi) / 2.0
        if mid > 0:
            diff_pct = (req.real_ms - mid) / mid * 100.0
    rec = {
        "ts": _dt.utcnow().isoformat(timespec="seconds") + "Z",
        "user": user,
        "sql": req.sql,
        "real_ms": req.real_ms,
        "predicted_cost": req.predicted_cost,
        "predicted_ms_lo": req.predicted_ms_lo,
        "predicted_ms_hi": req.predicted_ms_hi,
        "diff_pct": diff_pct,
        "source": req.source,
        "comment": req.comment,
        "trace_id": req.trace_id,
    }
    os.makedirs(os.path.dirname(_TIMING_LOG), exist_ok=True)
    # простая блокировка — одиночные дозаписи редкие
    with _th.Lock():
        with open(_TIMING_LOG, "a", encoding="utf-8") as f:
            f.write(_json.dumps(rec, ensure_ascii=False) + "\n")
    ev.log_event(user=user, endpoint="/timing/report", task="",
                 sql=req.sql, approved=True, iterations=None)
    return TimingReportResponse(ok=True, diff_pct=diff_pct)


# ─── /admin/* — HTTP Basic, статистика и выгрузка CSV ───────────────────────
@app.get("/admin/stats")
def admin_stats(_u: str = Depends(require_admin)) -> dict:
    """@brief Агрегаты по data/events.csv (для админ-дашборда)."""
    rows = ev.read_events()
    by_user: dict[str, dict] = {}
    by_table: dict[str, int] = {}
    by_vuln: dict[str, int] = {}
    approved_n = rejected_n = 0
    last_events: list[dict] = []

    for r in rows[-2000:]:                          # ограничиваем для скорости
        u = r.get("user") or "anonymous"
        bu = by_user.setdefault(u, {"requests": 0, "approved": 0, "rejected": 0,
                                    "tables": {}, "vulns": {}})
        bu["requests"] += 1
        if r.get("approved") == "true":
            bu["approved"] += 1
            approved_n += 1
        elif r.get("approved") == "false":
            bu["rejected"] += 1
            rejected_n += 1
        for t in (r.get("tables") or "").split(","):
            t = t.strip()
            if not t:
                continue
            by_table[t] = by_table.get(t, 0) + 1
            bu["tables"][t] = bu["tables"].get(t, 0) + 1
        for vc in (r.get("vuln_classes") or "").split(","):
            vc = vc.strip()
            if not vc:
                continue
            by_vuln[vc] = by_vuln.get(vc, 0) + 1
            bu["vulns"][vc] = bu["vulns"].get(vc, 0) + 1

    last_events = list(reversed(rows[-30:]))        # последние 30 для preview

    return {
        "total_events": len(rows),
        "approved": approved_n,
        "rejected": rejected_n,
        "users": [
            {"name": u, "requests": d["requests"],
             "approved": d["approved"], "rejected": d["rejected"],
             "top_tables": sorted(d["tables"].items(), key=lambda x: -x[1])[:5],
             "top_vulns":  sorted(d["vulns"].items(),  key=lambda x: -x[1])[:5]}
            for u, d in sorted(by_user.items(), key=lambda x: -x[1]["requests"])
        ],
        "top_tables": sorted(by_table.items(), key=lambda x: -x[1])[:15],
        "top_vulns":  sorted(by_vuln.items(),  key=lambda x: -x[1])[:15],
        "last_events": last_events,
    }


@app.get("/admin/export.csv")
def admin_export(_u: str = Depends(require_admin)):
    """@brief Скачать data/events.csv (сырой лог)."""
    path = ev.csv_path()
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="events.csv пуст — ещё не было запросов")
    return FileResponse(path, media_type="text/csv", filename="events.csv")
