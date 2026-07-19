from fastapi import Depends, FastAPI

from auth.dependencies import get_current_user
from auth.schemas import TokenPayload

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/me")
def me(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    return current_user
