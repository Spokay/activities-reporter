# Architecture Plan: Activities Reporter MCP Server

## Context

Build a REST API from scratch (the repo contains only a README) that generates AI-powered city activity reports and exposes them as MCP tools. An MCP client (e.g. OpenClaw) connects to `/mcp` and calls `create_report`, polls `get_report_by_id`, and reads the finished markdown. The stack is FastAPI + fastapi-mcp + Strands agents + SQLAlchemy (SQLite default, MariaDB in Docker).

---

## Data flow

```
MCP Client (OpenClaw)
        │  SSE  http://localhost:8002/mcp
        ▼
  FastApiMCP (0.4.0)
        │  derives tools from OpenAPI operation IDs
        ▼
  FastAPI app
   ├─ POST /api/reports     (operation_id="create_report")
   ├─ GET  /api/reports     (operation_id="get_reports")
   └─ GET  /api/reports/{id}(operation_id="get_report_by_id")
                │
                ▼  BackgroundTasks
        report_service.generate_report()
                │
                ├─ ResearcherAgent(AnthropicModel haiku-4-5, tavily tool)
                │       await agent.invoke_async(prompt) → research_text
                │
                └─ WriterAgent(AnthropicModel sonnet-4-6, no tools)
                        await agent.invoke_async(research_text) → markdown
                │
                ▼
        SQLAlchemy Session → reports table (SQLite / MariaDB)
```

---

## File structure (all new — repo is empty)

```
/
├── main.py
├── config.py
├── requirements.txt
├── docker-compose.yaml
├── Dockerfile
├── .env.example
├── auth/
│   ├── __init__.py
│   └── oidc.py            # build_auth_config() — optional OIDC setup
├── database/
│   ├── __init__.py
│   ├── engine.py          # init_engine(), get_db(), create_tables()
│   └── models.py          # Report ORM model, ReportStatus enum
├── schemas/
│   ├── __init__.py
│   └── report_schemas.py  # CreateReportRequest, ReportResponse
├── routes/
│   └── reports/
│       ├── __init__.py
│       └── report_router.py  # 3 endpoints
├── services/
│   ├── __init__.py
│   └── report_service.py  # generate_report() async
└── agents/
    ├── __init__.py
    ├── researcher_agent.py
    └── report_writer_agent.py
```

---

## 1. `requirements.txt`

```
strands-agents==1.40.0
strands-agents-tools==0.5.3
fastapi[standard]==0.136.1
fastapi-mcp==0.4.0
pydantic==2.13.3
pydantic-settings==2.14.1
sqlalchemy==2.0.49
pymysql==1.1.1
python-dotenv==1.0.0
```

---

## 2. `config.py`

```python
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    database_url: str = "sqlite:///./activities.db"
    anthropic_api_key: str
    tavily_api_key: str
    api_key: Optional[str] = None  # static key for remote deployment

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

---

## 3. `database/models.py`

```python
import enum, uuid
from datetime import datetime
from sqlalchemy import Column, String, Date, Text, DateTime, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func

class ReportStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done    = "done"
    failed  = "failed"

class Base(DeclarativeBase): pass

class Report(Base):
    __tablename__ = "reports"
    id            = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    city          = Column(String(255), nullable=False)
    start_date    = Column(Date, nullable=False)
    end_date      = Column(Date, nullable=False)
    status        = Column(SAEnum(ReportStatus), default=ReportStatus.pending, nullable=False)
    content       = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at    = Column(DateTime, server_default=func.now())
    updated_at    = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

`SAEnum` maps to `ENUM` on MariaDB and `VARCHAR` + CHECK constraint on SQLite — no manual migration needed.

---

## 4. `database/engine.py`

```python
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config import get_settings

_SessionLocal = None

def init_engine():
    global _SessionLocal
    engine = create_engine(get_settings().database_url)
    _SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    from .models import Base
    Base.metadata.create_all(engine)

def get_db():                          # FastAPI Depends target
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_session():                     # used by background tasks
    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

---

## 5. `schemas/report_schemas.py`

```python
from datetime import date
from typing import Optional
from pydantic import BaseModel
from database.models import ReportStatus

class CreateReportRequest(BaseModel):
    city: str
    start_date: date
    end_date: date

class ReportResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    city: str
    start_date: date
    end_date: date
    status: ReportStatus
    content: Optional[str] = None
    error_message: Optional[str] = None
```

---

## 6. `agents/researcher_agent.py`

```python
from strands import Agent
from strands.models import AnthropicModel
from strands_tools import tavily
from config import get_settings

_SYSTEM = (
    "You are a research agent. Use Tavily to find current events, activities, "
    "restaurants, and attractions for the given city and date range. "
    "Return comprehensive, raw findings."
)

def create_researcher_agent() -> Agent:
    s = get_settings()
    return Agent(
        model=AnthropicModel(
            model_id="claude-haiku-4-5-20251001",
            max_tokens=4096,
            client_args={"api_key": s.anthropic_api_key},
        ),
        tools=[tavily],
        system_prompt=_SYSTEM,
        callback_handler=None,
    )
```

A new instance is created per report to avoid shared conversation history.

---

## 7. `agents/report_writer_agent.py`

```python
from strands import Agent
from strands.models import AnthropicModel
from config import get_settings

_SYSTEM = (
    "You are a travel report writer. Format research findings into a structured "
    "markdown report with sections: Overview, Top Events, Food & Nightlife, "
    "Day-by-Day Activities, Practical Tips."
)

def create_writer_agent() -> Agent:
    s = get_settings()
    return Agent(
        model=AnthropicModel(
            model_id="claude-sonnet-4-6",
            max_tokens=8192,
            client_args={"api_key": s.anthropic_api_key},
        ),
        tools=[],
        system_prompt=_SYSTEM,
        callback_handler=None,
    )
```

---

## 8. `services/report_service.py`

```python
from datetime import date
from database.engine import get_session
from database.models import Report, ReportStatus
from agents.researcher_agent import create_researcher_agent
from agents.report_writer_agent import create_writer_agent

async def generate_report(report_id: str, city: str, start_date: date, end_date: date):
    with get_session() as db:
        report = db.get(Report, report_id)
        report.status = ReportStatus.running

    try:
        researcher = create_researcher_agent()
        writer     = create_writer_agent()

        research = await researcher.invoke_async(
            f"Research activities, events, restaurants and attractions in {city} "
            f"from {start_date} to {end_date}."
        )
        final = await writer.invoke_async(
            f"Format this research into a report:\n{research}"
        )

        with get_session() as db:
            report = db.get(Report, report_id)
            report.status  = ReportStatus.done
            report.content = str(final)

    except Exception as exc:
        with get_session() as db:
            report = db.get(Report, report_id)
            report.status        = ReportStatus.failed
            report.error_message = str(exc)
```

`invoke_async` is a native coroutine on `strands.Agent` — no `run_in_executor` wrapper needed.

---

## 9. `routes/reports/report_router.py`

```python
from uuid import uuid4
from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlalchemy.orm import Session
from database.engine import get_db
from database.models import Report, ReportStatus
from schemas.report_schemas import CreateReportRequest, ReportResponse
from services.report_service import generate_report
from typing import List

router = APIRouter()

@router.post("", status_code=202, operation_id="create_report",
             response_model=ReportResponse)
async def create_report(req: CreateReportRequest, bg: BackgroundTasks,
                        response: Response, db: Session = Depends(get_db)):
    # Return cached done report immediately (200)
    done = db.query(Report).filter_by(city=req.city, start_date=req.start_date,
                                      end_date=req.end_date, status=ReportStatus.done).first()
    if done:
        response.status_code = 200
        return ReportResponse.model_validate(done)

    # Return in-progress report (202) for deduplication
    running = db.query(Report).filter(
        Report.city == req.city, Report.start_date == req.start_date,
        Report.end_date == req.end_date,
        Report.status.in_([ReportStatus.pending, ReportStatus.running])
    ).first()
    if running:
        return ReportResponse.model_validate(running)

    report = Report(id=str(uuid4()), city=req.city,
                    start_date=req.start_date, end_date=req.end_date)
    db.add(report); db.commit(); db.refresh(report)
    bg.add_task(generate_report, report.id, req.city, req.start_date, req.end_date)
    return ReportResponse.model_validate(report)


@router.get("", operation_id="get_reports", response_model=List[ReportResponse])
def get_reports(city: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Report)
    if city:
        q = q.filter(Report.city == city)
    return [ReportResponse.model_validate(r) for r in q.all()]


@router.get("/{report_id}", operation_id="get_report_by_id", response_model=ReportResponse)
def get_report_by_id(report_id: str, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return ReportResponse.model_validate(report)
```

---

## 10. `main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
from database.engine import init_engine
from routes.reports.report_router import router as reports_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()   # creates tables on first boot
    yield

app = FastAPI(title="Activities Reporter", lifespan=lifespan)
app.include_router(reports_router, prefix="/api/reports")

mcp = FastApiMCP(app)
mcp.mount()         # SSE at /mcp, messages at /mcp/messages
```

`FastApiMCP` derives the three MCP tools from the operation IDs automatically.

---

## 11. `docker-compose.yaml`

```yaml
version: "3.9"
services:
  activities-db:
    image: mariadb:11
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: activities
      MYSQL_USER: activities
      MYSQL_PASSWORD: activities
    ports:
      - "3306:3306"
    volumes:
      - mariadb_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 10s
      timeout: 5s
      retries: 5

  activities-reporter:
    build: .
    ports:
      - "8002:8002"
    environment:
      DATABASE_URL: mysql+pymysql://activities:activities@activities-db/activities
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      TAVILY_API_KEY: ${TAVILY_API_KEY}
    depends_on:
      activities-db:
        condition: service_healthy
    command: uvicorn main:app --host 0.0.0.0 --port 8002

volumes:
  mariadb_data:
```

---

## 12. Auth — OAuth 2.0 / OIDC (fastapi-mcp 0.4.0)

OpenClaw supports the MCP 2025-03-26 OAuth spec, so we wire up full OIDC via `fastapi-mcp`'s `AuthConfig`. The library proxies your OIDC provider's endpoints, exposes `/.well-known/oauth-authorization-server`, and handles the `authorization_code` + PKCE flow.

### New config fields (`config.py`)

```python
oauth_issuer: Optional[str] = None          # e.g. "https://your-tenant.auth0.com"
oauth_client_id: Optional[str] = None
oauth_client_secret: Optional[str] = None
oauth_audience: Optional[str] = None        # some providers need this
```

### Auth factory (`auth/oidc.py`)

```python
from typing import Optional
from fastapi_mcp.types import AuthConfig

def build_auth_config(issuer: str, client_id: str,
                      client_secret: str, audience: Optional[str] = None) -> AuthConfig:
    return AuthConfig(
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
        audience=audience,
        setup_proxies=True,              # fastapi-mcp proxies /oauth/authorize, /oauth/token
        setup_fake_dynamic_registration=True,  # required by mcp-remote-style clients
    )
```

`fastapi-mcp` mounts:
- `GET  /.well-known/oauth-authorization-server` — metadata (MCP spec required)
- `GET  /oauth/authorize` — proxies to OIDC provider
- `POST /oauth/register` — fake dynamic client registration
- token exchange handled by the provider directly

### Updated `main.py`

```python
from auth.oidc import build_auth_config

settings = get_settings()
auth_config = None
if settings.oauth_issuer and settings.oauth_client_id:
    auth_config = build_auth_config(
        settings.oauth_issuer,
        settings.oauth_client_id,
        settings.oauth_client_secret,
        settings.oauth_audience,
    )

mcp = FastApiMCP(app, auth_config=auth_config)
mcp.mount()
```

When `OAUTH_*` env vars are absent the server runs without auth (useful for local dev). Set them for any deployment exposed beyond localhost.

### `.env.example` additions

```
OAUTH_ISSUER=https://your-tenant.auth0.com
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_AUDIENCE=https://activities-reporter.example.com   # optional
```

### OpenClaw `openclaw.json` — no extra fields needed

Once `OAUTH_*` is configured, the server advertises its `/.well-known/oauth-authorization-server` endpoint and OpenClaw drives the full consent flow automatically:

```json
{
  "mcpServers": {
    "activities-reporter": {
      "transport": "sse",
      "url": "http://localhost:8002/mcp"
    }
  }
}
```

---

## Verification

1. **Install & boot:** `pip install -r requirements.txt && uvicorn main:app --port 8002`
2. **SQLite table created:** check `activities.db` exists with a `reports` table
3. **Create report:**
   ```
   curl -X POST http://localhost:8002/api/reports \
     -H "Content-Type: application/json" \
     -d '{"city":"Paris","start_date":"2026-05-17","end_date":"2026-05-18"}'
   ```
   → 202 `{"id":"...","status":"pending",...}`
4. **Poll:**
   ```
   curl http://localhost:8002/api/reports/<id>
   ```
   → eventually `"status":"done"` with markdown in `content`
5. **MCP tools:** `curl http://localhost:8002/mcp` → SSE stream listing `create_report`, `get_reports`, `get_report_by_id`
6. **OpenClaw:** configure `openclaw.json`, ask *"What should I do in Paris this weekend?"*
7. **Docker stack:** `docker compose up` → switch `DATABASE_URL` to MariaDB and re-run steps 3–4