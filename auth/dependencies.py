import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from auth.schemas import TokenPayload
from auth.security import decode_access_token

# tokenUrl points to S-01's future endpoint — informational only for OpenAPI UI.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenPayload:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        return decode_access_token(token)
    except (jwt.InvalidTokenError, KeyError):
        raise credentials_exception
