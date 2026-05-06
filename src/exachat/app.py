"""Streamlit app for exachat."""

from __future__ import annotations

import os
import time
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from exachat.app_builder import render_builder, render_metrics_tab
from exachat.core import ExasolChat, QueryResult
from exachat.connection import ConnectionConfig
from exachat.llm import OllamaBackend, OpenAICompatibleBackend
from exachat.safety import RiskLevel

load_dotenv()

_DEFAULT_DUCKDB_PATH    = os.environ.get("EXACHAT_DUCKDB_PATH", "")
_DEFAULT_OLLAMA_URL     = os.environ.get("EXACHAT_OLLAMA_URL", "http://localhost:11434")
_DEFAULT_OLLAMA_MODEL   = os.environ.get("EXACHAT_OLLAMA_MODEL", "qwen2.5-coder:7b")
_DEFAULT_KB_PATH        = os.environ.get("EXACHAT_KB_PATH", "")
_DEFAULT_METRICS_PATH   = os.environ.get("EXACHAT_METRICS_PATH", "")


# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="⚡ exachat",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom styles — Claude-inspired palette ───────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    .block-container { padding-top: 1.5rem; max-width: 1100px; }
    code, pre, .stCode { font-family: 'JetBrains Mono', monospace !important; }

    /* Compact app header */
    header[data-testid="stHeader"],
    .stAppHeader {
        height: 2.75rem !important;
        min-height: 2.75rem !important;
    }

    [data-testid="stSidebar"] { background-color: #1a1a1a; }
    [data-testid="stSidebar"] * { color: #e8e8e8 !important; }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stTextInput label,
    [data-testid="stSidebar"] .stTextArea label,
    [data-testid="stSidebar"] .stNumberInput label { color: #a0a0a0 !important; font-size: 0.8rem !important; }

    [data-testid="stChatMessage"] {
        border-radius: 12px; padding: 0.75rem 1rem; margin-bottom: 0.5rem;
    }

    .badge-safe {
        display: inline-block; padding: 2px 10px; border-radius: 20px;
        background: rgba(34, 197, 94, 0.12); color: #22c55e;
        font-size: 0.75rem; font-weight: 600; letter-spacing: 0.02em;
    }
    .badge-warn {
        display: inline-block; padding: 2px 10px; border-radius: 20px;
        background: rgba(251, 146, 60, 0.12); color: #fb923c;
        font-size: 0.75rem; font-weight: 600; letter-spacing: 0.02em;
    }
    .badge-blocked {
        display: inline-block; padding: 2px 10px; border-radius: 20px;
        background: rgba(239, 68, 68, 0.12); color: #ef4444;
        font-size: 0.75rem; font-weight: 600; letter-spacing: 0.02em;
    }

    .kb-indicator { font-size: 0.73rem; color: #9ca3af; margin-top: 6px; }

    .col-warning {
        background: rgba(251, 191, 36, 0.08); border-left: 3px solid #fbbf24;
        padding: 6px 10px; border-radius: 4px; font-size: 0.82rem;
        color: #d97706; margin-bottom: 6px;
    }

    .schema-table-name { font-weight: 600; font-size: 0.9rem; color: #f97316; }
    .schema-row-count  { font-size: 0.75rem; color: #6b7280; }

    /* Follow-up suggestion pills */
    div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
        background: rgba(249, 115, 22, 0.08) !important;
        border: 1px solid rgba(249, 115, 22, 0.3) !important;
        color: #f97316 !important;
        border-radius: 20px !important;
        font-size: 0.82rem !important;
        padding: 4px 14px !important;
    }
    div[data-testid="stHorizontalBlock"] button[kind="secondary"]:hover {
        background: rgba(249, 115, 22, 0.15) !important;
    }

    .stButton > button[kind="primary"] { background: #f97316; border: none; }
    .stButton > button[kind="primary"]:hover { background: #ea6c0a; }

    /* Tab labels — target the actual <p> inside stMarkdownContainer inside stTab */
    button[data-testid="stTab"] p {
        color: #b0b0b0 !important;
        font-size: 0.92rem !important;
        font-weight: 500 !important;
        margin: 0 !important;
    }
    button[data-testid="stTab"]:hover p {
        color: #ffffff !important;
    }
    button[data-testid="stTab"][aria-selected="true"] p {
        color: #f97316 !important;
        font-weight: 600 !important;
    }
    [data-baseweb="tab-highlight"] {
        background-color: #f97316 !important;
    }
    [data-baseweb="tab-border"] {
        background-color: #2d2d2d !important;
    }

    /* Sticky tab bar — stays accessible while scrolling */
    [data-testid="stTabs"] > div:first-child,
    div[data-baseweb="tabs"] > div:first-child,
    div[role="tablist"] {
        position: -webkit-sticky !important;
        position: sticky !important;
        top: 2.75rem !important;
        z-index: 100 !important;
        background-color: #0e1117 !important;
        padding-bottom: 2px !important;
    }
</style>
""", unsafe_allow_html=True)


# ── Session state ────────────────────────────────────────────────────
if "chat" not in st.session_state:
    st.session_state.chat = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "connected" not in st.session_state:
    st.session_state.connected = False
if "explore_questions" not in st.session_state:
    st.session_state.explore_questions = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None
if "open_in_builder" not in st.session_state:
    st.session_state.open_in_builder = None
if "db_preview" not in st.session_state:
    st.session_state.db_preview = None

_VIZ_KEYWORDS = {"chart", "graph", "plot", "visuali", "diagram", "bar", "line", "pie", "scatter", "trend"}


def _wants_viz(question: str) -> bool:
    q = question.lower()
    return any(k in q for k in _VIZ_KEYWORDS)


# ── DB preview helper ─────────────────────────────────────────────────

def _fetch_db_preview(conn_type: str, **kwargs) -> dict:
    """Temporarily connect to fetch available schemas and tables.

    Returns {"schemas": [...], "tables_by_schema": {"schema": ["table", ...]}}
    """
    schemas: list[str] = []
    tables_by_schema: dict[str, list[str]] = {}

    if conn_type == "DuckDB":
        import duckdb
        path = kwargs.get("path", ":memory:")
        conn = duckdb.connect(database=path, read_only=(path != ":memory:"))
        try:
            df = conn.execute(
                "SELECT DISTINCT table_schema, table_name "
                "FROM information_schema.tables "
                "WHERE table_schema NOT IN ('information_schema', 'pg_catalog') "
                "ORDER BY table_schema, table_name"
            ).fetchdf()
            schemas = df["table_schema"].unique().tolist()
            for _, row in df.iterrows():
                tables_by_schema.setdefault(row["table_schema"], []).append(row["table_name"])
        finally:
            conn.close()

    elif conn_type == "Exasol (pyexasol)":
        import pyexasol
        conn = pyexasol.connect(
            dsn=kwargs["dsn"], user=kwargs["user"],
            password=kwargs["password"], compression=True,
        )
        try:
            stmt = conn.execute(
                "SELECT DISTINCT TABLE_SCHEMA, TABLE_NAME "
                "FROM EXA_ALL_TABLES ORDER BY 1, 2"
            )
            rows = stmt.fetchall()
            schemas = list(dict.fromkeys(r[0] for r in rows))
            for r in rows:
                tables_by_schema.setdefault(r[0], []).append(r[1])
        finally:
            conn.close()

    else:  # SQLAlchemy
        from sqlalchemy import create_engine, inspect
        engine = create_engine(kwargs["url"])
        try:
            insp = inspect(engine)
            schemas = insp.get_schema_names()
            for s in schemas:
                try:
                    tables_by_schema[s] = insp.get_table_names(schema=s)
                except Exception:
                    tables_by_schema[s] = []
        finally:
            engine.dispose()

    return {"schemas": schemas, "tables_by_schema": tables_by_schema}


# ── Helper functions ─────────────────────────────────────────────────

import re as _re

def _clean_summary(text: str) -> str:
    """Strip markdown bold/italic markers that cause rendering artifacts.

    LLM summaries sometimes wrap numbers or words in *asterisks* which
    Streamlit renders as italic/bold, breaking readability.
    """
    # Remove bold (**text**) and italic (*text* / _text_) markers
    text = _re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = _re.sub(r"\*([^*]+)\*", r"\1", text)
    text = _re.sub(r"_([^_]+)_", r"\1", text)
    return text


def _render_chart_dynamic(
    r: QueryResult,
    df: pd.DataFrame,
    selected: list[str],
    dim_cols: list[str],
    chart_type_override: str | None = None,
    x_override: str | None = None,
) -> bool:
    """Render a chart using the selected measure columns.

    Falls back gracefully: uses the LLM chart config as hints for chart
    type and x-axis, then builds with plotly. chart_type_override and
    x_override take precedence over the LLM suggestion when provided.
    """
    if not selected or df.empty:
        return False

    cfg = r.chart_config or {}
    chart_type = chart_type_override or cfg.get("chart_type", "bar")
    if chart_type == "table_only":
        return False

    # Pick x-axis: user override → LLM suggestion → first dim col
    if x_override and x_override in df.columns:
        x_col = x_override
    else:
        x_col = cfg.get("x")
        if not x_col or x_col not in df.columns:
            x_col = dim_cols[0] if dim_cols else None
    if not x_col:
        return False

    try:
        import plotly.express as px
        y = selected[0] if len(selected) == 1 else selected

        if chart_type == "line":
            fig = px.line(df, x=x_col, y=y)
        elif chart_type == "area":
            fig = px.area(df, x=x_col, y=y)
        elif chart_type == "scatter":
            fig = px.scatter(df, x=x_col, y=selected[0])
        elif chart_type == "pie" and len(selected) == 1:
            fig = px.pie(df, names=x_col, values=selected[0])
        else:
            # bar — grouped when multiple measures
            barmode = "group" if len(selected) > 1 else "relative"
            fig = px.bar(df, x=x_col, y=y, barmode=barmode)

        fig.update_layout(margin=dict(t=30, b=0), legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)
        return True
    except Exception:
        return False


def _render_result(r: QueryResult, elapsed: float | None = None):
    key = hash(r.question)

    if r.error:
        st.error(r.error)
        if r.sql:
            with st.expander("🔍 Generated SQL"):
                st.code(r.sql, language="sql")
        return

    if r.column_warnings:
        for w in r.column_warnings:
            st.markdown(f'<div class="col-warning">{w}</div>', unsafe_allow_html=True)

    if r.summary:
        st.markdown(_clean_summary(r.summary))

    with st.expander("🔍 Generated SQL", expanded=False):
        if r.safety.level == RiskLevel.SAFE:
            badge = '<span class="badge-safe">✓ Safe</span>'
        elif r.safety.level == RiskLevel.SUSPICIOUS:
            badge = f'<span class="badge-warn">⚠ {r.safety.reason}</span>'
        else:
            badge = f'<span class="badge-blocked">✕ Blocked: {r.safety.reason}</span>'
        st.markdown(badge, unsafe_allow_html=True)
        st.code(r.sql, language="sql")
        if r.explanation:
            st.caption(r.explanation)
        if r.kb_patterns_used > 0:
            st.markdown(
                f'<div class="kb-indicator">📖 {r.kb_patterns_used} KB pattern{"s" if r.kb_patterns_used != 1 else ""} guided this query</div>',
                unsafe_allow_html=True,
            )

    if elapsed is not None:
        st.markdown(
            f'<div style="font-size:0.88rem;color:#6b7280;margin:4px 0 12px;font-weight:500;">⏱ {elapsed:.1f}s</div>',
            unsafe_allow_html=True,
        )

    if r.data is not None and len(r.data) > 0:
        df = r.data
        num_cols = df.select_dtypes(include="number").columns.tolist()
        dim_cols = df.select_dtypes(exclude="number").columns.tolist()
        has_chart_data = len(num_cols) >= 1 and len(df.columns) >= 2

        # ── Viz control bar: chart-type | x-axis (dimension) | measures ──
        ctl1, ctl2, ctl3 = st.columns([2, 2, 4])
        with ctl1:
            viz_choice = st.selectbox(
                "Chart type",
                ["auto", "bar", "line", "area", "scatter", "pie", "table only"],
                key=f"viz_{key}",
                help="Override the AI-suggested chart type",
                label_visibility="collapsed",
            )

        # Resolve effective chart behaviour
        if viz_choice == "table only":
            chart_type_override = "table_only"
            show_chart = False
        elif viz_choice == "auto":
            chart_type_override = None
            show_chart = (
                has_chart_data
                and r.chart_obj is not None
                and (r.chart_config or {}).get("chart_type") != "table_only"
            )
        else:
            chart_type_override = viz_choice
            show_chart = has_chart_data

        # X-axis / dimension selector
        x_override: str | None = None
        with ctl2:
            if show_chart and dim_cols:
                _all_xax = dim_cols + [c for c in num_cols if c not in dim_cols]
                x_override = st.selectbox(
                    "X axis",
                    _all_xax,
                    key=f"xax_{key}",
                    help="Column to use as the X axis / dimension",
                    label_visibility="collapsed",
                )

        # Measure multiselect — shown when chart is on + 2+ numeric cols
        selected_measures = num_cols
        with ctl3:
            if show_chart and len(num_cols) > 1:
                selected_measures = st.multiselect(
                    "📊 Measures",
                    options=num_cols,
                    default=num_cols,
                    key=f"ms_{key}",
                    help="Choose which measures to display in the chart",
                    label_visibility="collapsed",
                )

        # ── Chart rendering ────────────────────────────────────────
        chart_rendered = False
        if show_chart and selected_measures:
            if chart_type_override or x_override or len(num_cols) > 1:
                chart_rendered = _render_chart_dynamic(
                    r, df, selected_measures, dim_cols,
                    chart_type_override, x_override,
                )
            elif r.chart_obj:
                lib, chart = r.chart_obj
                if lib == "plotly":
                    st.plotly_chart(chart, use_container_width=True)
                elif lib == "altair":
                    st.altair_chart(chart, use_container_width=True)
                chart_rendered = True

        # ── Data table ────────────────────────────────────────────
        skip_table = chart_rendered and _wants_viz(r.question)
        if not skip_table:
            st.dataframe(df, use_container_width=True, height=min(400, 35 * len(df) + 50))

        col_dl, col_gap = st.columns([1, 6])
        with col_dl:
            st.download_button(
                "📥 CSV", df.to_csv(index=False), "query_result.csv", "text/csv",
                use_container_width=True, key=f"dl_{key}",
            )

    # Follow-up suggestions
    if r.followups:
        st.markdown(
            '<div style="font-size:0.75rem;color:#6b7280;margin-top:12px;margin-bottom:4px;">💡 Suggested follow-ups</div>',
            unsafe_allow_html=True,
        )
        cols = st.columns(len(r.followups))
        for i, (col, q) in enumerate(zip(cols, r.followups)):
            with col:
                if st.button(q, key=f"fu_{key}_{i}", use_container_width=True):
                    st.session_state.pending_question = q
                    st.rerun()


# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ exachat")

    st.divider()

    # ── 1. DATABASE ───────────────────────────────────────────────────
    st.markdown("#### Database")
    _conn_options = ["DuckDB", "Exasol (pyexasol)", "SQLAlchemy URL"]
    conn_type = st.selectbox("Connection type", _conn_options)

    if st.session_state.get("_prev_conn_type") != conn_type:
        st.session_state.db_preview = None
        st.session_state["_prev_conn_type"] = conn_type

    if conn_type == "Exasol (pyexasol)":
        exa_host = st.text_input("Host:Port", placeholder="host:8563")
        exa_user = st.text_input("Username")
        exa_pass = st.text_input("Password", type="password")
    elif conn_type == "DuckDB":
        duck_path = st.text_input(
            "Database path",
            value=_DEFAULT_DUCKDB_PATH,
            placeholder=":memory: or /path/to/file.duckdb",
        )
    else:
        db_url = st.text_input("Connection URL", placeholder="sqlite:///data.db")

    if st.button("🔍 Load schemas & tables", key="b_db_preview", use_container_width=True):
        try:
            with st.spinner("Connecting…"):
                _kw: dict = {}
                if conn_type == "DuckDB":
                    _kw["path"] = duck_path or ":memory:"
                elif conn_type == "Exasol (pyexasol)":
                    _kw.update(dsn=exa_host, user=exa_user, password=exa_pass)
                else:
                    _kw["url"] = db_url
                st.session_state.db_preview = _fetch_db_preview(conn_type, **_kw)
        except Exception as _pe:
            st.error(f"Preview failed: {_pe}")

    _preview = st.session_state.db_preview

    st.divider()

    # ── 2. ACCESS CONTROL (includes schema selector) ──────────────────
    st.markdown("#### Access Control")

    # Schema selector
    if conn_type == "Exasol (pyexasol)":
        if _preview:
            _exa_opts = ["(none)"] + _preview["schemas"]
            _exa_sel = st.selectbox("Schema", _exa_opts, key="exa_schema_sel")
            exa_schema = "" if _exa_sel == "(none)" else _exa_sel
        else:
            exa_schema = st.text_input("Schema", placeholder="MY_SCHEMA")
    elif conn_type == "DuckDB":
        if _preview:
            _duck_schemas = _preview["schemas"]
            _duck_idx = _duck_schemas.index("main") if "main" in _duck_schemas else 0
            duck_schema = st.selectbox("Schema", _duck_schemas, index=_duck_idx, key="duck_schema_sel")
        else:
            duck_schema = st.text_input("Schema", value="main")

    # Table restriction
    if _preview:
        _ac_schema: str | None = None
        if conn_type == "Exasol (pyexasol)":
            _ac_schema = exa_schema or None
        elif conn_type == "DuckDB":
            _ac_schema = duck_schema or None

        if _ac_schema and _ac_schema in _preview["tables_by_schema"]:
            _avail_tables = _preview["tables_by_schema"][_ac_schema]
        else:
            _avail_tables = sorted({t for ts in _preview["tables_by_schema"].values() for t in ts})

        _n_total = sum(len(v) for v in _preview["tables_by_schema"].values())
        st.caption(f"{_n_total} tables · {len(_preview['schemas'])} schemas")

        _ac_tables_sel = st.multiselect(
            "Restrict tables (optional)",
            _avail_tables,
            key="ac_tables_sel",
            help="Leave empty to allow all tables in the selected schema",
        )
        allowed_schemas_str = _ac_schema or ""
        allowed_tables_str  = ",".join(_ac_tables_sel)
    else:
        allowed_schemas_str = st.text_input(
            "Allowed schemas",
            placeholder="SALES, ANALYTICS",
        )
        allowed_tables_str = st.text_input(
            "Allowed tables",
            placeholder="CUSTOMERS, ORDERS",
        )

    st.divider()

    # ── 3. CONNECT / SESSION BUTTONS ──────────────────────────────────
    # Seed session_state defaults once (avoids value= + key= conflict in widgets below).
    _sb_defaults = {
        "_sb_llm_type":      "Ollama",
        "_sb_ollama_url":    _DEFAULT_OLLAMA_URL   or "http://localhost:11434",
        "_sb_ollama_model":  _DEFAULT_OLLAMA_MODEL or "llama3.1:8b",
        "_sb_api_url":       "http://localhost:1234/v1",
        "_sb_api_model":     "local-model",
        "_sb_api_key":       "not-needed",
        "_sb_extra_context": "",
        "_sb_max_rows":      5000,
        "_sb_chart_lib":     "auto",
        "_sb_kb_path":       _DEFAULT_KB_PATH      or "",
        "_sb_metrics_path":  _DEFAULT_METRICS_PATH or "",
    }
    for _k, _v in _sb_defaults.items():
        if _k not in st.session_state:
            st.session_state[_k] = _v

    # Now read them for use in the Connect handler (widgets below keep them in sync).
    _llm_type     = st.session_state["_sb_llm_type"]
    _ollama_url   = st.session_state["_sb_ollama_url"]
    _ollama_model = st.session_state["_sb_ollama_model"]
    _api_url      = st.session_state["_sb_api_url"]
    _api_model    = st.session_state["_sb_api_model"]
    _api_key      = st.session_state["_sb_api_key"]
    _extra_ctx    = st.session_state["_sb_extra_context"]
    _max_rows     = int(st.session_state["_sb_max_rows"])
    _chart_lib    = st.session_state["_sb_chart_lib"]
    _kb_path      = st.session_state["_sb_kb_path"]
    _metrics_path = st.session_state["_sb_metrics_path"]

    _btn_label = "✅ Connected — reconnect" if st.session_state.connected else "⚡ Connect"
    if st.button(_btn_label, use_container_width=True, type="primary"):
        try:
            with st.spinner("Connecting & reading schema..."):
                if conn_type == "Exasol (pyexasol)":
                    if not exa_host or not exa_user or not exa_pass:
                        st.error("Fill in host, user, and password.")
                        st.stop()
                    config = ConnectionConfig.exasol(
                        dsn=exa_host, user=exa_user, password=exa_pass,
                        schema=exa_schema or None,
                    )
                elif conn_type == "DuckDB":
                    if not duck_path:
                        st.error("Enter a database path.")
                        st.stop()
                    config = ConnectionConfig.duckdb(path=duck_path)
                else:
                    if not db_url:
                        st.error("Enter a database URL.")
                        st.stop()
                    config = ConnectionConfig.from_url(db_url)

                if _llm_type == "Ollama":
                    llm = OllamaBackend(model=_ollama_model, base_url=_ollama_url)
                else:
                    llm = OpenAICompatibleBackend(
                        base_url=_api_url, model=_api_model, api_key=_api_key,
                    )

                allowed_schemas = None
                if allowed_schemas_str.strip():
                    allowed_schemas = [s.strip() for s in allowed_schemas_str.split(",") if s.strip()]
                allowed_tables = None
                if allowed_tables_str.strip():
                    allowed_tables = [t.strip() for t in allowed_tables_str.split(",") if t.strip()]

                if conn_type == "Exasol (pyexasol)":
                    schema_param = exa_schema or None
                elif conn_type == "DuckDB":
                    schema_param = duck_schema if duck_schema and duck_schema != "main" else None
                else:
                    schema_param = None

                chat = ExasolChat(
                    connection=config,
                    llm=llm,
                    schema=schema_param,
                    allowed_schemas=allowed_schemas,
                    allowed_tables=allowed_tables,
                    extra_context=_extra_ctx,
                    max_rows=_max_rows,
                    kb_path=_kb_path.strip() or None,
                    chart_library=_chart_lib,
                    metrics_path=_metrics_path.strip() or None,
                )

            st.session_state.chat = chat
            st.session_state.connected = True
            st.session_state.messages = []
            st.session_state.pending_question = None

            with st.spinner("Generating starter questions..."):
                st.session_state.explore_questions = chat.generate_explore_questions()

            st.success(
                f"Connected! {len(chat.schema_context.tables)} tables "
                f"({chat.schema_context.dialect})"
            )
        except Exception as e:
            st.error(f"Connection failed: {e}")

    if st.session_state.connected and st.session_state.chat:
        col_nc, col_dc = st.columns(2)
        with col_nc:
            if st.button("🗨️ New Chat", use_container_width=True,
                         help="Keep connection, clear conversation"):
                st.session_state.chat.clear_history()
                st.session_state.messages = []
                st.session_state.pending_question = None
                st.rerun()
        with col_dc:
            if st.button("🔌 Disconnect", use_container_width=True,
                         help="Close connection and start over"):
                try:
                    st.session_state.chat.close()
                except Exception:
                    pass
                st.session_state.chat = None
                st.session_state.connected = False
                st.session_state.messages = []
                st.session_state.db_preview = None
                st.rerun()

    st.divider()

    # ── 4. LLM BACKEND ────────────────────────────────────────────────
    with st.expander("🤖 LLM Backend", expanded=not st.session_state.connected):
        llm_type = st.selectbox(
            "Backend", ["Ollama", "OpenAI-compatible API"], key="_sb_llm_type",
        )
        if llm_type == "Ollama":
            st.text_input("URL",   key="_sb_ollama_url")
            st.text_input("Model", key="_sb_ollama_model")
        else:
            st.text_input("API URL", key="_sb_api_url")
            st.text_input("Model",   key="_sb_api_model")
            st.text_input("API Key", key="_sb_api_key", type="password")

    # ── 5. KNOWLEDGE BASE ─────────────────────────────────────────────
    with st.expander("📖 Knowledge Base", expanded=False):
        st.text_input(
            "Extra KB directory",
            key="_sb_kb_path",
            placeholder="/path/to/kb/",
            help="Built-in patterns are always loaded. Set EXACHAT_KB_PATH in .env to pre-fill.",
        )
        if st.session_state.connected and st.session_state.chat:
            st.caption(f"{st.session_state.chat.kb.count} SQL patterns loaded.")

    # ── 6. METRICS CATALOG ────────────────────────────────────────────
    with st.expander("📐 Metrics Catalog", expanded=False):
        st.text_input(
            "Metrics directory",
            key="_sb_metrics_path",
            placeholder="~/.exachat/metrics/",
            help="Set EXACHAT_METRICS_PATH in .env to pre-fill.",
        )

    # ── 7. OPTIONS ────────────────────────────────────────────────────
    with st.expander("⚙️ Options", expanded=False):
        st.text_area(
            "Extra context / DDL",
            key="_sb_extra_context",
            placeholder="Business rules, column descriptions...",
            height=80,
        )
        st.number_input("Max rows", key="_sb_max_rows", min_value=100, max_value=50000)
        st.selectbox("Chart library", ["auto", "plotly", "altair"], key="_sb_chart_lib")

    # ── 8. SCHEMA EXPLORER (when connected) ───────────────────────────
    if st.session_state.connected and st.session_state.chat:
        st.divider()
        chat_ref = st.session_state.chat
        with st.expander(f"📋 Schema ({len(chat_ref.schema_context.tables)} tables)", expanded=False):
            for table in chat_ref.schema_context.tables:
                label = f'<div class="schema-table-name">{table.name}</div>'
                if table.row_count is not None:
                    label += f'<div class="schema-row-count">{table.row_count:,} rows</div>'
                st.markdown(label, unsafe_allow_html=True)
                cols_text = " · ".join(f"`{c.name}` {c.type}" for c in table.columns[:8])
                if len(table.columns) > 8:
                    cols_text += f" · ... +{len(table.columns) - 8} more"
                st.caption(cols_text)


# ── Main area ────────────────────────────────────────────────────────
if not st.session_state.connected:
    st.markdown("## ⚡ exachat")
    st.markdown(
        "Connect to your database in the sidebar, then ask questions in plain English. "
        "Powered by local LLMs and a built-in SQL pattern knowledge base."
    )
    st.info(
        "**Prerequisites:** Ollama running locally (or any OpenAI-compatible API) "
        "and a database to connect to."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### Python API")
        st.code(
            'from exachat import ExasolChat\n\n'
            'chat = ExasolChat(\n'
            '    "duckdb:///data.duckdb"\n'
            ')\n'
            'result = chat.ask("Top 10 customers by revenue")\n'
            'print(result.data)',
            language="python",
        )
    with col2:
        st.markdown("#### DuckDB")
        st.code(
            'from exachat import ExasolChat\n\n'
            'chat = ExasolChat("./analytics.duckdb")\n\n'
            'result = chat.ask("Monthly trends")\n'
            'print(result.summary)',
            language="python",
        )
    with col3:
        st.markdown("#### CLI")
        st.code(
            '# Install\n'
            'pip install exachat\n\n'
            '# Launch\n'
            'exachat',
            language="bash",
        )
    st.stop()


# ── Connected — inject top-right status badge ─────────────────────────
_chat_ref = st.session_state.chat
_dial = (_chat_ref.schema_context.dialect or "DB").upper()
_n_tables = len(_chat_ref.schema_context.tables)
st.markdown(
    f'<div style="position:fixed;top:0.45rem;right:1.2rem;z-index:9999;'
    f'background:#0d1f0d;border:1px solid rgba(34,197,94,0.55);border-radius:6px;'
    f'padding:3px 12px;font-size:0.72rem;color:#22c55e;font-weight:600;'
    f'letter-spacing:0.03em;box-shadow:0 1px 4px rgba(0,0,0,0.4);">'
    f'✅ {_dial} · {_n_tables} tables</div>',
    unsafe_allow_html=True,
)

# ── Tabbed interface ─────────────────────────────────────────────────
chat_engine: ExasolChat = st.session_state.chat

# JS reinforcement for sticky tabs (CSS alone unreliable inside Streamlit's scroll container)
import streamlit.components.v1 as _stc
_stc.html(
    """<script>
    (function stickyTabs() {
        const doc = window.parent.document;
        function apply() {
            // Try multiple selectors in priority order
            const candidates = [
                doc.querySelector('[data-testid="stTabs"] > div:first-child'),
                doc.querySelector('div[data-baseweb="tabs"] > [role="tablist"]'),
                doc.querySelector('div[role="tablist"]'),
            ];
            for (const el of candidates) {
                if (el) {
                    el.style.position  = 'sticky';
                    el.style.top       = '2.75rem';
                    el.style.zIndex    = '100';
                    el.style.background = '#0e1117';
                    el.style.paddingBottom = '2px';
                    break;
                }
            }
        }
        apply();
        // Re-apply after Streamlit re-renders
        setTimeout(apply, 400);
        setTimeout(apply, 1200);
    })();
    </script>""",
    height=0,
)

tab_ask, tab_build, tab_metrics, tab_schema = st.tabs(
    ["💬 Ask", "📊 Build", "📐 Metrics", "🗺️ Schema"]
)

# ── ASK tab ──────────────────────────────────────────────────────────
with tab_ask:
    # Explore question grid — shown only before the first message
    if not st.session_state.messages and st.session_state.explore_questions:
        st.markdown("#### Where do you want to start?")
        eq = st.session_state.explore_questions
        row1, row2 = eq[:3], eq[3:]
        for row in [row1, row2]:
            cols = st.columns(len(row))
            for col, q in zip(cols, row):
                with col:
                    if st.button(q, use_container_width=True, key=f"eq_{hash(q)}"):
                        st.session_state.pending_question = q
                        st.rerun()
        st.divider()

    # Render conversation history — always drives the display order
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            elif "result" in msg:
                _render_result(msg["result"], elapsed=msg.get("elapsed"))
            else:
                st.markdown(msg.get("content", ""))

    # Collect next question (typed or from a button)
    pending = st.session_state.get("pending_question")
    if pending:
        st.session_state.pending_question = None

    typed = st.chat_input("Ask a question about your data...")
    question = typed or pending

    if question:
        # Store the user turn, process, store the assistant turn, then rerun.
        # This keeps the chat_input anchored at the bottom and ensures each
        # follow-up appears as a new entry below the previous one.
        st.session_state.messages.append({"role": "user", "content": question})
        with st.spinner("Thinking…"):
            _t0 = time.perf_counter()
            result = chat_engine.ask(question)
            _elapsed = time.perf_counter() - _t0
        st.session_state.messages.append({
            "role": "assistant",
            "result": result,
            "elapsed": _elapsed,
        })
        st.rerun()

# ── BUILD tab ────────────────────────────────────────────────────────
with tab_build:
    # If "Open in Builder" was clicked in the Ask tab, seed the builder
    open_sql = st.session_state.pop("open_in_builder", None)
    if open_sql and chat_engine.builder:
        seeded = chat_engine.builder.seed_from_sql(open_sql)
        # Only seed if the table was found and it exists in the schema
        if seeded.get("table") and seeded["table"] in chat_engine.builder.table_names():
            st.session_state.builder = seeded
            st.session_state.pop("builder_result", None)

    render_builder(chat_engine, chat_engine.builder, chat_engine.metrics_catalog)

# ── METRICS tab ──────────────────────────────────────────────────────
with tab_metrics:
    render_metrics_tab(chat_engine.metrics_catalog)

# ── SCHEMA MAP tab ────────────────────────────────────────────────────
with tab_schema:
    import re as _re2
    from exachat.schema import get_join_map

    tables = chat_engine.schema_context.tables
    jmap   = get_join_map(tables)

    st.markdown("### 🗺️ Schema Relationship Map")
    st.caption(
        "Auto-generated ER diagram. Solid lines = exact column-name match. "
        "Dashed = similar name. Grey tables have no detected join path."
    )

    if not tables:
        st.info("No tables loaded.")
    else:
        # ── Build Mermaid erDiagram ────────────────────────────────
        def _m_name(s: str) -> str:
            """Safe Mermaid entity / attribute identifier (must start with a letter)."""
            name = _re2.sub(r"[^a-zA-Z0-9_]", "_", s).strip("_") or "col"
            if name[0].isdigit() or name[0] == "_":
                name = "n" + name
            return name

        def _m_type(col_type: str) -> str:
            """Single-word SQL type for Mermaid attribute declarations."""
            base = _re2.split(r"[\s(]", col_type.strip())[0]
            return _re2.sub(r"[^a-zA-Z0-9_]", "", base) or "VARCHAR"

        mer_lines = ["erDiagram"]

        for t in tables:
            ename = _m_name(t.name)
            mer_lines.append(f"    {ename} {{")
            for c in t.columns[:30]:
                atype = _m_type(c.type)
                aname = _m_name(c.name)
                markers = ""
                if c.primary_key:
                    markers = " PK"
                elif c.foreign_key:
                    markers = " FK"
                mer_lines.append(f"        {atype} {aname}{markers}")
            if len(t.columns) > 30:
                extra = len(t.columns) - 30
                mer_lines.append(f"        varchar more{extra}cols")
            mer_lines.append("    }")

        for j in jmap["joins"]:
            t1  = _m_name(j["t1"])
            t2  = _m_name(j["t2"])
            c1s = _m_name(j["c1"])
            c2s = _m_name(j["c2"])
            lbl = c1s if c1s == c2s else f"{c1s}_{c2s}"
            rel = "||--|{" if j["match"] == "exact" else "||..|{"
            mer_lines.append(f'    {t1} {rel} {t2} : "{lbl}"')

        mermaid_src = "\n".join(mer_lines)

        # Estimate iframe height based on total column count
        _total_rows = sum(min(len(t.columns), 30) + 3 for t in tables)
        _height = max(500, min(1200, _total_rows * 24 + len(tables) * 60))

        # JSON-encode the source so special chars in names are safe in JS
        import json as _json
        import base64 as _b64
        _mer_js = _json.dumps(mermaid_src)

        _html_page = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>
  html, body {{ margin: 0; padding: 0; background: #0e1117; overflow: auto; }}
  #diagram svg {{ max-width: 100% !important; }}
  #errmsg {{ color: #f88; font-family: monospace; white-space: pre-wrap; padding: 12px; }}
</style>
</head>
<body>
<div id="diagram"></div>
<script>
  mermaid.initialize({{
    startOnLoad: false,
    theme: 'dark',
    er: {{
      layoutDirection: 'LR',
      diagramPadding: 24,
      entityPadding: 14,
      useMaxWidth: true
    }}
  }});
  mermaid.render('er1', {_mer_js}).then(function(r) {{
    document.getElementById('diagram').innerHTML = r.svg;
  }}).catch(function(e) {{
    document.getElementById('diagram').innerHTML =
      '<pre id="errmsg">Mermaid render error:\\n' + e.message + '</pre>';
  }});
</script>
</body>
</html>"""

        _iframe_src = "data:text/html;base64," + _b64.b64encode(_html_page.encode()).decode()
        if hasattr(st, "iframe"):
            st.iframe(_iframe_src, height=_height)
        else:
            _stc.html(_html_page, height=_height, scrolling=True)

        with st.expander("🔍 Mermaid source", expanded=False):
            st.code(mermaid_src, language="text")

    st.divider()

    # ── Join summary panels ────────────────────────────────────────
    col_jp, col_nj = st.columns(2)

    with col_jp:
        st.markdown("#### ✅ Detected join paths")
        if jmap["joins"]:
            for j in jmap["joins"]:
                badge_color = "#22c55e" if j["match"] == "exact" else "#fb923c"
                badge_label = j["match"]
                st.markdown(
                    f'`{j["t1"]}.{j["c1"]}` **=** `{j["t2"]}.{j["c2"]}` &nbsp;'
                    f'<span style="color:{badge_color};font-size:0.74rem">{badge_label}</span>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No shared columns detected between any table pair.")

    with col_nj:
        st.markdown("#### ⚠️ No direct join path")
        if jmap["no_join"]:
            st.caption(
                "These pairs share no column — requires an intermediate table. "
                "The LLM is told not to attempt direct JOINs between them."
            )
            for t1, t2 in jmap["no_join"]:
                st.markdown(
                    f'`{t1}` **↔** `{t2}` '
                    '<span style="color:#ef4444;font-size:0.74rem">no shared column</span>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("All table pairs have at least one detected join path.")

    st.divider()

    # ── Join summary panels ────────────────────────────────────────
    col_jp, col_nj = st.columns(2)

    with col_jp:
        st.markdown("#### ✅ Detected join paths")
        if jmap["joins"]:
            for j in jmap["joins"]:
                badge_color = "#22c55e" if j["match"] == "exact" else "#fb923c"
                badge_label = j["match"]
                st.markdown(
                    f'`{j["t1"]}.{j["c1"]}` **=** `{j["t2"]}.{j["c2"]}` &nbsp;'
                    f'<span style="color:{badge_color};font-size:0.74rem">{badge_label}</span>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No shared columns detected between any table pair.")

    with col_nj:
        st.markdown("#### ⚠️ No direct join path")
        if jmap["no_join"]:
            st.caption(
                "These pairs share no column — requires an intermediate table. "
                "The LLM is told not to attempt direct JOINs between them."
            )
            for t1, t2 in jmap["no_join"]:
                st.markdown(
                    f'`{t1}` **↔** `{t2}` '
                    '<span style="color:#ef4444;font-size:0.74rem">no shared column</span>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("All table pairs have at least one detected join path.")
