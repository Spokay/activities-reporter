from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi_mcp import FastApiMCP

from auth.jwt import verify_token
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


@app.middleware("http")
async def mcp_auth_middleware(request: Request, call_next):
    if not get_settings().oauth_issuer or request.url.path != "/mcp":
        return await call_next(request)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing Bearer token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        await verify_token(auth_header.removeprefix("Bearer "))
    except HTTPException:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await call_next(request)

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
mcp.mount_http()
