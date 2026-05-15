from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
from auth.oidc import build_auth_config
from config import get_settings
from database.engine import init_engine
from routes.reports.report_router import router as reports_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()
    yield


app = FastAPI(title="Activities Reporter", lifespan=lifespan)
app.include_router(reports_router, prefix="/api/reports")

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
