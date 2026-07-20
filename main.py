from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status

from auth.dependencies import get_current_user
from auth.schemas import TokenPayload
from database import _get_engine, close_engine, engine_health_check
from routers.auth import router as auth_router
from routers.events import router as events_router
from routers.reports import router as reports_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    _get_engine()
    yield
    await close_engine()


app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(reports_router)


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
