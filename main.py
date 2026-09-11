import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from auth.dependencies import get_current_user
from auth.schemas import TokenPayload
from database import _get_engine, close_engine, engine_health_check
from routers.analysis import router as analysis_router
from routers.auth import router as auth_router
from routers.events import router as events_router
from routers.reports import router as reports_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    _get_engine()
    yield
    await close_engine()


app = FastAPI(lifespan=lifespan)

# CORS — the SPA is served from a separate origin in production and calls this
# API cross-origin. Allowed origins come from FRONTEND_ORIGIN (comma-separated),
# with localhost defaults for dev. In dev the Vite proxy makes calls same-origin,
# so these localhost entries are a harmless belt-and-suspenders.
_cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"] + [
    o.strip() for o in os.getenv("FRONTEND_ORIGIN", "").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(events_router)
app.include_router(reports_router)
app.include_router(analysis_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/me")
def me(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    return current_user


@app.get("/api/health/db")
async def health_db():
    ok = await engine_health_check()
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="db unavailable",
        )
    return {"db": "ok"}
