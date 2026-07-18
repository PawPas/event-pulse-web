import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
import jwt

from auth.schemas import TokenPayload

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


# lru_cache means one os.getenv syscall per process lifetime.
# If a test needs a different SECRET_KEY, call _secret_key.cache_clear() first.
@lru_cache(maxsize=1)
def _secret_key() -> str:
    key = os.getenv("SECRET_KEY")
    if not key:
        raise RuntimeError("SECRET_KEY environment variable must be set")
    return key


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(
    subject: str,
    email: str,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "email": email, "exp": expire}
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    # Raises jwt.InvalidTokenError on expired, bad signature, or malformed token.
    # Does NOT raise HTTPException — that is the dependency's responsibility.
    payload = jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
    return TokenPayload(sub=payload["sub"], email=payload["email"])
