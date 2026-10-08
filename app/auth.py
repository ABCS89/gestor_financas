import os
import time
import hmac
import hashlib
from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException, Depends, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "financas123")
SECRET_KEY = os.getenv("SECRET_KEY", "chave-secreta-gestor-financas-2026").encode()

COOKIE_NAME = "finance_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 dias


class LoginRequest(BaseModel):
    username: str
    password: str


def create_signed_token(username: str) -> str:
    timestamp = str(int(time.time()))
    payload = f"{username}:{timestamp}"
    signature = hmac.new(SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def verify_signed_token(token: str) -> Optional[str]:
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        username, timestamp_str, received_sig = parts
        timestamp = int(timestamp_str)
        # Verifica expiração (30 dias)
        if time.time() - timestamp > SESSION_MAX_AGE:
            return None
        payload = f"{username}:{timestamp_str}"
        expected_sig = hmac.new(SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_sig, received_sig):
            return username
    except Exception:
        return None
    return None


def get_current_user(request: Request) -> Optional[str]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        # Permite passar via header Authorization: Bearer <token> se preferir
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        return None

    return verify_signed_token(token)


def require_auth(request: Request) -> str:
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado. Por favor, faça login."
        )
    return user


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    user_ok = hmac.compare_digest(payload.username.strip().lower(), ADMIN_USERNAME.strip().lower())
    pass_ok = hmac.compare_digest(payload.password, ADMIN_PASSWORD)

    if not user_ok or not pass_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos."
        )

    token = create_signed_token(ADMIN_USERNAME)
    # Define cookie seguro
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False  # Funciona tanto em HTTP local quanto HTTPS no Render
    )

    return {"message": "Login realizado com sucesso!", "username": ADMIN_USERNAME}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME)
    return {"message": "Logout realizado com sucesso."}


@router.get("/me")
def check_me(request: Request):
    user = get_current_user(request)
    return {
        "authenticated": user is not None,
        "username": user if user else None
    }
