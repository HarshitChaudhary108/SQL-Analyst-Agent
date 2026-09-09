# Data Analyst Agent

An AI agent that answers natural language questions about a PostgreSQL database by autonomously generating, validating, and executing SQL queries — then explaining the results in plain English. Built with [LangGraph](https://www.langchain.com/langgraph) for orchestration and LLMs for reasoning.

## Overview

Data Analyst Agent turns a plain-English question (e.g. *"total payments done where user id is '5455'?"*) into a safe, executable SQL query and a human-readable answer — without the user needing to know any SQL or the underlying database schema.

The agent works in stages:

1. **Curate the question** — refines/cleans the user's raw question using an LLM.
2. **Build context** — pulls live schema details (tables, columns, data types, and sample rows) from the target PostgreSQL database.
3. **Generate SQL** — an LLM writes a Postgres-compatible SQL query grounded in the actual schema.
4. **Judge safety** — a separate LLM "judge" checks the query is read-only (blocks `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `CREATE`, etc.) before anything touches the database.
5. **Execute or cancel** — safe queries are run against the database; unsafe queries are rejected with a reason.
6. **Summarize** — the execution result is translated back into a clear, non-technical final answer.

This project ships with a sample **ride-sharing (Uber-style)** database schema — `users`, `vehicles`, `rides`, `payments`, and `ratings` — used to demo the agent end-to-end.

## Features

- **Natural language → SQL** — no manual query writing required.
- **Schema-aware prompting** — the agent introspects the live database (tables, columns, types, sample data) so generated queries match the real schema.
- **Built-in safety guardrail** — an LLM-as-judge node blocks any query that isn't a pure read (`SELECT`), preventing accidental or malicious writes.
- **Graph-based orchestration** — the pipeline is modeled as a directed graph (LangGraph `StateGraph`) with conditional branching for safe vs. unsafe queries.
- **Human-friendly answers** — raw SQL results are converted into plain-language responses.
- **Configurable LLM tiers** — different steps use different model "strengths" (`low` / `medium` / `hard`) via a `pick_llm` utility, so cost/latency can be tuned per task.
- **Database seeding script** — `feed_db.py` sets up the schema and bulk-loads CSV data via PostgreSQL's `COPY` for fast ingestion.

## Project Structure

```
data-analyst-agent/
├── agent/
│   ├── __init__.py
│   └── sql_analyst.py       # LangGraph pipeline: curate → prompt → generate SQL → judge → execute → summarize
├── agent_schema/
│   ├── __init__.py
│   └── schema.py             # AgentSchema (graph state) and JudgeSchema (structured safety verdict)
├── utils/
│   ├── database.py           # DatabaseUtil: connection handling + live schema introspection
│   └── pick_llm.py           # Selects an LLM by task difficulty tier (low/medium/hard)
├── data/                     # CSV source files for seeding the database (users, vehicles, rides, payments, ratings)
├── feed_db.py                 # Creates tables/indexes and bulk-loads CSVs into PostgreSQL
├── main.py                    # Application entry point
├── schema_details.txt         # Cached/exported snapshot of the live DB schema
├── .env                        # Environment variables (DB credentials, API keys) — not committed
├── pyproject.toml
└── uv.lock
```

## How It Works (Agent Graph)

```
START
  └─▶ curate_question
        └─▶ prompt_query
              └─▶ generate_sql_query
                    └─▶ is_safe
                          ├─ Yes ─▶ execute_sql_query ─▶ represent_final_answer ─▶ END
                          └─ No  ─▶ canceled_sql_query ─▶ represent_final_answer ─▶ END
```

- **`curate_question`** — cleans up the raw user question with a low-tier LLM.
- **`prompt_query`** — fetches live schema + sample data via `DatabaseUtil.schema_details()` and assembles the SQL-generation prompt.
- **`generate_sql_query`** — a higher-tier LLM produces the SQL query (limited to 10 rows unless the user specifies otherwise).
- **`is_safe`** — a judge LLM returns a structured `Yes`/`No` verdict (plus reasoning) on whether the query is read-only.
- **`execute_sql_query`** — runs the query via `psycopg2` and captures the result set (or the error, if execution fails).
- **`canceled_sql_query`** — short-circuits with an explanation when a query is judged unsafe.
- **`represent_final_answer`** — a medium-tier LLM turns the raw result set into a concise, user-facing answer.

## Tech Stack

- **Language:** Python 3.x
- **Package Management:** [uv](https://github.com/astral-sh/uv)
- **Orchestration:** [LangGraph](https://www.langchain.com/langgraph) (`StateGraph`)
- **LLM Integration:** LangChain core with structured output (`with_structured_output`) for schema-validated judge responses
- **Database:** PostgreSQL via `psycopg2`
- **Config:** `python-dotenv` for environment variable management

## Prerequisites

- Python (version pinned in `.python-version`)
- [uv](https://github.com/astral-sh/uv) for dependency management
- A running PostgreSQL instance
- API key(s) for your chosen LLM provider(s)

## Setup

1. Clone the repository and install dependencies:
   ```bash
   git clone <repository-url>
   cd data-analyst-agent
   uv sync
   ```

2. Create a `.env` file in the project root with your database and LLM credentials:
   ```env
   host=<db-host>
   port=<db-port>
   user=<db-user>
   password=<db-password>
   database=<db-name>

   # LLM provider API key(s), e.g.:
   # GROQ_API_KEY=your_key_here
   ```

3. Seed the database with the sample ride-sharing schema and data:
   ```bash
   uv run feed_db.py
   ```
   This creates the `users`, `vehicles`, `rides`, `payments`, and `ratings` tables (plus indexes) and bulk-loads the corresponding CSVs from the `data/` directory.

## Usage

Run the agent directly:

```bash
uv run main.py
```

Or invoke the graph programmatically:

```python
from agent.sql_analyst import sql_analyst

initial_state = {
    "messages": [],
    "user_question": "total payments done where user id is '5455'?",
    "curated_ques": "",
    "prompt_query": "",
    "is_safe": "",
    "generated_sql_query": "",
    "comments": "",
    "sql_execution_result": "",
    "final_answer": ""
}

final_state = sql_analyst.invoke(initial_state)

print(final_state["final_answer"])
print(final_state["generated_sql_query"])
print(final_state["sql_execution_result"])
```

## Safety Notes

- The agent is restricted to **read-only** operations by design — the `is_safe` node explicitly checks for and blocks any data-modifying SQL (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `CREATE`).
- Database credentials are read from environment variables and should never be committed to version control — ensure `.env` is listed in `.gitignore`.
- Even with the safety judge in place, review generated queries in sensitive/production environments before granting the agent broader database access.