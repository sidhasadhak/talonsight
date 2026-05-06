# ⚡ exachat

**Ask your database anything — in plain English. Get SQL, data, and interactive charts.**

Local LLMs only. No data leaves your machine. Works with DuckDB, Exasol, PostgreSQL, MySQL, SQLite, and anything SQLAlchemy supports.

![Ask tab — query result with interactive bar chart](docs/images/screenshot-ask.png)

---

## Features

- **Natural language → SQL** — powered by any local LLM (Ollama, LM Studio, vLLM, etc.)
- **4 tabs**: Ask (chat), Build (visual query builder), Metrics (saved KPIs), Schema (ER diagram)
- **Interactive charts** — Plotly bar, line, area, scatter, pie with live controls for chart type, x-axis, and measures
- **Visual Query Builder** — table / dimension / measure selector with filters, sort, and limit — no SQL required
- **Schema Relationship Map** — auto-generated Mermaid ER diagram with detected join paths
- **Metrics Catalog** — define, save, and reuse KPI queries with one click
- **Knowledge Base** — saves successful question→SQL pairs; injects similar patterns as few-shot examples into the prompt
- **Join inference** — detects join paths by exact and fuzzy column-name matching; explicitly warns the LLM about table pairs that cannot be joined
- **Access Control** — restrict queries to specific schemas and/or tables; SQL safety validator (allowlist SELECT/WITH only)
- **DuckDB dialect hints** — built-in prompt guidance for `QUALIFY`, `GROUP BY ALL`, `TRY_CAST`, date functions, and more
- **Pre-fill with `.env`** — set default paths, model, and URL so the UI is ready on launch

---

## Install

```bash
pip install exachat          # DuckDB, PostgreSQL, SQLite, MySQL
pip install exachat[exasol]  # + Exasol (pyexasol + sqlalchemy-exasol)
pip install exachat[all]     # everything
```

**Requirements:** Python ≥ 3.9, and a local LLM server (see [LLM setup](#llm-setup) below).

---

## Quick Start

### 1. Get a local LLM running

```bash
# Install Ollama (macOS / Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model — qwen2.5-coder:7b is the recommended starting point
ollama pull qwen2.5-coder:7b    # ✅ Best quality/speed balance
ollama pull qwen2.5-coder:14b   # Better quality, slower
ollama pull deepseek-coder-v2:16b  # Excellent for complex queries
```

Using **LM Studio** or **vLLM**? Choose **"OpenAI-compatible API"** in the sidebar's LLM Backend expander.

### 2. Launch the UI

```bash
exachat
```

Opens at `http://localhost:8501`.

### 3. Connect

The sidebar keeps the most important controls above the fold:

1. **Database** — pick connection type (DuckDB / Exasol / SQLAlchemy URL) and enter credentials or a file path
2. Click **🔍 Load schemas & tables** to preview available schemas (optional but recommended — enables dropdowns)
3. **Access Control** — select the schema and optionally restrict to specific tables
4. Click **⚡ Connect**

Advanced settings — LLM backend, Knowledge Base path, Metrics directory, and Options — are in collapsed expanders below the buttons.

![Compact sidebar and auto-generated starter questions](docs/images/screenshot-connected.png)

After connecting, exachat generates 5 starter questions based on your actual schema and data profile.

### 4. Ask questions

Type in plain English — exachat generates SQL, runs it read-only, and shows a plain-English summary, an interactive chart, and the raw data table.

Use the **chart controls** row below each answer to switch chart type, change the x-axis, or select which measures to plot — without re-running the query.

### 5. Pre-fill with a `.env` file

Create `.env` in your working directory (gitignored):

```bash
EXACHAT_DUCKDB_PATH=/path/to/your/database.duckdb
EXACHAT_OLLAMA_URL=http://localhost:11434
EXACHAT_OLLAMA_MODEL=qwen2.5-coder:7b
```

---

## The Four Tabs

### 💬 Ask — Natural Language Chat

Type a question, get SQL + a plain-English summary + an interactive Plotly chart + the raw data table.

- Click **👍** to save the question→SQL pair to the Knowledge Base so future similar questions benefit from it
- Follow-up questions work naturally — "now filter by last 90 days", "also show average order value"
- Every answer shows a **Generated SQL** expander, timing, and suggested follow-up questions

### 📊 Build — Visual Query Builder

Pick a table, add dimensions (GROUP BY columns) and measures (aggregated columns with SUM / AVG / COUNT / MIN / MAX), set filters, sort order, and row limit — then click **▶ Run**.

The builder generates clean, schema-qualified SQL and renders the same interactive chart + table as the Ask tab. Dimensions can be reordered with ↑↓ buttons. Great for ad-hoc exploration without writing SQL.

![Visual Query Builder — field configuration](docs/images/screenshot-build-config.png)

![Visual Query Builder — results with chart and data table](docs/images/screenshot-build-result.png)

### 📐 Metrics — Saved KPIs

Define a metric once (name + SQL or question), save it to the Metrics Catalog, and re-run it in any future session with one click. Metrics persist to disk as JSON files in the configured directory.

### 🗺️ Schema — ER Diagram

Auto-generated entity-relationship diagram using Mermaid.js. Tables show all column names and their SQL data types. Solid lines indicate exact column-name join paths; dashed lines indicate fuzzy root matches (e.g. `order_id` ↔ `order_id_pseudonyms`). Tables with no detected join path are shown in isolation.

![Schema Relationship Map — auto-generated Mermaid ER diagram](docs/images/screenshot-schema.png)

---

## Python API

```python
from exachat import ExasolChat

# DuckDB (local file)
chat = ExasolChat("duckdb:///path/to/analytics.duckdb")
chat = ExasolChat("./my_data.duckdb")  # bare path works too

# Exasol
chat = ExasolChat("exa+pyexasol://user:pass@host:8563/MY_SCHEMA")

# PostgreSQL
chat = ExasolChat("postgresql://user:pass@localhost:5432/mydb")

# SQLite / MySQL / anything SQLAlchemy supports
chat = ExasolChat("sqlite:///local.db")
chat = ExasolChat("mysql+pymysql://user:pass@host:3306/db")
```

```python
result = chat.ask("Top 10 customers by total spend")

print(result.summary)      # "The top customer is Acme Corp with $2.3M..."
print(result.sql)          # SELECT customer_name, SUM(total) AS total_spend ...
print(result.data)         # pandas DataFrame
print(result.chart_config) # {"chart_type": "bar", "x": "customer_name", ...}
```

### Using a different LLM backend

```python
from exachat.llm import OpenAICompatibleBackend

llm = OpenAICompatibleBackend(
    base_url="http://localhost:1234/v1",
    model="qwen2.5-coder-14b",
)
chat = ExasolChat("./data.duckdb", llm=llm)
```

### Access control

```python
chat = ExasolChat(
    "exa+pyexasol://readonly_user:pass@host:8563/PROD",
    allowed_schemas=["SALES", "ANALYTICS"],
    allowed_tables=["CUSTOMERS", "ORDERS", "PRODUCTS"],
    extra_context="""
        - revenue columns are in EUR
        - fiscal year starts April 1
        - ORDERS.status: 'active', 'cancelled', 'refunded'
    """,
)
```

### Scripting / batch reports

```python
from exachat import ExasolChat

with ExasolChat("duckdb:///sales.duckdb") as chat:
    monthly = chat.ask("Monthly revenue for the last 12 months")
    top_products = chat.ask("Top 5 products by units sold this quarter")

    monthly.data.to_csv("monthly_revenue.csv", index=False)
    top_products.data.to_csv("top_products.csv", index=False)
```

### Inspect what the LLM sees

```python
chat = ExasolChat("duckdb:///data.duckdb")
print(chat.schema_prompt)  # Full schema context including join hints
```

---

## LLM Setup

### Ollama (recommended)

| Model | Command | Quality | Speed | Notes |
|-------|---------|---------|-------|-------|
| `qwen2.5-coder:7b` | `ollama pull qwen2.5-coder:7b` | ⭐⭐⭐⭐ | Fast | **Recommended default** |
| `qwen2.5-coder:14b` | `ollama pull qwen2.5-coder:14b` | ⭐⭐⭐⭐⭐ | Medium | Best quality/speed tradeoff |
| `deepseek-coder-v2:16b` | `ollama pull deepseek-coder-v2:16b` | ⭐⭐⭐⭐⭐ | Medium | Excellent for complex joins |
| `sqlcoder:7b` | `ollama pull sqlcoder:7b` | ⭐⭐⭐⭐ | Fast | Fine-tuned for SQL |
| `llama3.1:8b` | `ollama pull llama3.1:8b` | ⭐⭐⭐ | Fast | Good general-purpose fallback |

### OpenAI-compatible APIs

Any server implementing `/v1/chat/completions` works — LM Studio, vLLM, text-generation-webui, LocalAI. Select **"OpenAI-compatible API"** in the LLM Backend expander and enter the base URL and model name.

---

## Knowledge Base

Successful question→SQL pairs are stored locally and retrieved for similar future questions — injected as few-shot examples into the LLM prompt. Uses ChromaDB with a lightweight offline embedding; no model download required.

```python
# On by default. Disable:
chat = ExasolChat("...", rag_enabled=False)

# Seed with your own patterns:
chat.train(
    "quarterly revenue by region",
    """SELECT region,
        date_trunc('quarter', order_date) AS quarter,
        SUM(amount) AS revenue
    FROM sales.orders
    GROUP BY ALL
    ORDER BY quarter, revenue DESC"""
)

# Inspect stored pairs:
print(chat.kb.count)
print(chat.kb.list_all())

# Clear memory:
chat.rag.clear()
```

Patterns persist at `~/.exachat/rag/` by default. Point the UI to a custom directory via the **📖 Knowledge Base** expander or `EXACHAT_KB_PATH` in `.env`.

---

## Safety Model

- **Allowlist-only**: Only `SELECT` and `WITH` (CTE) pass. `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `EXEC`, `CALL`, `EXPORT`, `IMPORT`, `COPY`, `ATTACH`, `DETACH`, `INSTALL`, `LOAD` are all blocked before execution.
- **No `exec()` or `eval()`**: LLM output is never executed as Python code.
- **Pattern matching**: Blocks `read_csv` / `read_parquet` / `read_json` (DuckDB file access), `pg_sleep`, `BENCHMARK`, statement stacking (`;`-separated queries), `SET`, `PRAGMA`.
- **Access control enforcement**: The LLM prompt explicitly lists allowed tables; the safety validator cross-checks the generated SQL against the allowlist.
- **Read-only connections**: DuckDB files always opened with `read_only=True`. SQLAlchemy uses `SET TRANSACTION READ ONLY` where supported.
- **Suspicious query warnings**: `UNION SELECT`, tautology injections, and system table access trigger a visible warning badge without blocking execution.

> Use a **read-only database user** in production. The safety layer is defence-in-depth, not a substitute for proper DB permissions.

---

## Architecture

```
Question
  │
  ├─► Knowledge Base retrieval (similar Q→SQL patterns as few-shot examples)
  │
  ▼
LLM Prompt
  ├── Schema context (tables, columns, types, row counts)
  ├── Join map (detected paths + "no-join" table pairs)
  ├── DuckDB dialect hints (if applicable)
  ├── Few-shot KB examples
  └── Conversation history (follow-up support)
  │
  ▼
SQL Generation → Safety Validation → Query Execution (read-only)
  │
  ▼
Summary · Chart · DataFrame · Follow-up Suggestions · KB feedback loop
```

### Module map

| Module | Purpose |
|--------|---------|
| `app.py` | Streamlit UI — 4 tabs (Ask / Build / Metrics / Schema), compact sidebar, chart controls |
| `app_builder.py` | Visual Query Builder — dimension / measure / filter / sort UI → SQL |
| `core.py` | Engine — orchestrates the full `ask()` pipeline |
| `llm.py` | LLM backends — Ollama + OpenAI-compatible; DuckDB dialect hints; prompt construction |
| `schema.py` | Schema introspection + join inference (exact + fuzzy column-name matching) |
| `safety.py` | SQL validation — allowlist, DDL/DML blocking, injection pattern detection |
| `connection.py` | Connection management — pyexasol, DuckDB native (read-only), SQLAlchemy |
| `builder.py` | QueryBuilder — programmatic SELECT / GROUP BY / filter / sort → schema-qualified SQL |
| `metrics.py` | Metrics Catalog — save / load / run named KPI queries from JSON |
| `kb.py` | Knowledge Base — offline ChromaDB store for Q→SQL patterns |
| `charts.py` | Auto-charting — Plotly bar / line / area / scatter / pie / heatmap |

---

## Configuration Reference

```python
from exachat import ExasolChat
from exachat.llm import OllamaBackend

chat = ExasolChat(
    connection="duckdb:///sales.duckdb",
    llm=OllamaBackend(model="qwen2.5-coder:7b"),

    # Schema scoping
    schema="main",

    # Access control
    allowed_schemas=["SALES", "ANALYTICS"],
    allowed_tables=["CUSTOMERS", "ORDERS", "PRODUCTS"],

    # Business context injected into every prompt
    extra_context="revenue is in EUR. fiscal year starts April 1.",

    # Query limits
    max_rows=10000,

    # Knowledge Base
    rag_enabled=True,
    kb_path=None,          # path to extra KB JSON files (built-in patterns always loaded)

    # Charts
    chart_library="auto",  # "plotly", "altair", or "auto"

    # Metrics
    metrics_path=None,     # path to metrics JSON directory (~/.exachat/metrics/ by default)
)
```

---

## Limitations

- **SQL accuracy = LLM quality.** Smaller models produce worse SQL. 7B+ recommended; 14B+ for complex schemas or many tables.
- **Safety layer is regex-based.** It catches known patterns but is not a full SQL parser. Always use a read-only database user.
- **Join inference is heuristic.** Column-name similarity works well for conventional naming; semantic joins (different names, same concept) are not detected.
- **Charts are LLM-suggested.** Usually correct — use the chart controls in the UI to override type, axes, and measures.
- **Knowledge Base similarity is bag-of-words.** Works well for SQL Q&A; not as precise as dense embedding models.

---

## License

MIT
