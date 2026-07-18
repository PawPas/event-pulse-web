from pydantic import BaseModel


class TokenPayload(BaseModel):
    sub: str  # user_id as string; S-01 will carry this through to the DB User
    email: str
