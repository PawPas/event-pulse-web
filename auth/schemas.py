from pydantic import BaseModel


class TokenPayload(BaseModel):
    sub: str  # user_id as string; S-01 will carry this through to the DB User
    email: str


class UserRegister(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
