# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Dev (SQLite, no Docker)
pip install -r requirements.txt
cp .env.example .env   # fill ANTHROPIC_API_KEY and TAVILY_API_KEY
uvicorn main:app --reload --port 8002

# Docker (MariaDB)
docker compose up --build

# API docs
open http://localhost:8002/docs
```

No test suite yet. Validate manually via `/docs` or the MCP endpoint.

## Architecture

FastAPI app exposing a report generation API, also mounted as an MCP server via `fastapi-mcp`.

**Request flow:**
1. `POST /api/reports` — router checks DB for existing/in-progress report; creates new `Report` row (status=`pending`), enqueues `generate_report` as a FastAPI `BackgroundTask`.
2. `generate_report` (service) runs two **Strands** agents sequentially:
   - **Researcher** (`claude-haiku-4-5`) — uses Tavily web search to gather raw activity data.
   - **Writer** (`claude-sonnet-4-6`) — formats researcher output into structured markdown.
3. Report content and final status (`done`/`failed`) written back to DB.
4. `GET /api/reports/{id}` — poll for completion.

**Key design decisions:**
- Reports are deduplicated by `(city, start_date, end_date)`: identical completed reports return 200; in-progress ones return 202 with the existing record.
- DB schema is auto-created on startup via `Base.metadata.create_all` in `init_engine()`.
- Default DB is SQLite (`activities.db`). Switch to MariaDB by setting `DATABASE_URL=mysql+pymysql://...`.
- OAuth/OIDC is optional. When `OAUTH_ISSUER` + `OAUTH_CLIENT_ID` are set, `fastapi-mcp` enforces auth on the MCP mount.

## Required env vars

| Var | Purpose |
|-----|---------|
| `ANTHROPIC_API_KEY` | Strands agents |
| `TAVILY_API_KEY` | Researcher agent web search |
| `DATABASE_URL` | SQLAlchemy URL (default: SQLite) |

Optional OAuth vars: `OAUTH_ISSUER`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `OAUTH_AUDIENCE`.

## Module map

| Path | Role |
|------|------|
| `main.py` | App factory, router registration, MCP mount |
| `config.py` | `Settings` via pydantic-settings (reads `.env`) |
| `database/engine.py` | Engine init, `get_db` (FastAPI dep), `get_session` (context manager for background tasks) |
| `database/models.py` | `Report` ORM model, `ReportStatus` enum |
| `agents/researcher_agent.py` | Strands agent with Tavily tool |
| `agents/report_writer_agent.py` | Strands agent, no tools |
| `services/report_service.py` | Orchestrates both agents, updates DB |
| `routes/reports/report_router.py` | CRUD endpoints |
| `schemas/report_schemas.py` | Pydantic request/response models |
| `auth/oidc.py` | Builds `AuthConfig` for fastapi-mcp |