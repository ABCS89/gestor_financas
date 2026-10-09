import os
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import require_auth
from app.services.gdrive_service import (
    test_drive_connection,
    get_stored_config,
    save_stored_config,
    sync_drive_receipts,
    get_oauth_authorization_url,
    handle_oauth_callback,
    disconnect_gdrive,
    get_oauth_client_config
)

router = APIRouter(prefix="/api/gdrive", tags=["Google Drive"])


class GDriveConfigPayload(BaseModel):
    folder_id: str


class OAuthCredentialsPayload(BaseModel):
    client_id: str
    client_secret: str


@router.get("/status")
def get_gdrive_status(user: str = Depends(require_auth)):
    status = test_drive_connection()
    config = get_stored_config()
    status["folder_id"] = config.get("folder_id", "")
    oauth_configured = get_oauth_client_config() is not None
    status["oauth_configured"] = oauth_configured
    return status


@router.post("/config")
def set_gdrive_config(payload: GDriveConfigPayload, user: str = Depends(require_auth)):
    config = get_stored_config()
    folder_id = payload.folder_id.strip()
    if "folders/" in folder_id:
        folder_id = folder_id.split("folders/")[-1].split("?")[0]
    
    config["folder_id"] = folder_id
    save_stored_config(config)
    return {"message": "Configuração da pasta salva com sucesso!", "folder_id": folder_id}


@router.post("/oauth-credentials")
def save_oauth_credentials(payload: OAuthCredentialsPayload, user: str = Depends(require_auth)):
    creds_data = {
        "web": {
            "client_id": payload.client_id.strip(),
            "client_secret": payload.client_secret.strip(),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
        }
    }
    with open("credentials.json", "w", encoding="utf-8") as f:
        json.dump(creds_data, f, indent=2)
    return {"message": "Credenciais OAuth salvas com sucesso!"}


@router.get("/auth/url")
def get_auth_url(request: Request, user: str = Depends(require_auth)):
    redirect_uri = os.getenv("GDRIVE_REDIRECT_URI")
    if not redirect_uri:
        base_url = str(request.base_url).rstrip("/")
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            base_url = f"{forwarded_proto}://{request.url.netloc}"
        redirect_uri = f"{base_url}/api/gdrive/auth/callback"

    auth_url = get_oauth_authorization_url(redirect_uri)
    if not auth_url:
        raise HTTPException(
            status_code=400,
            detail="Credenciais do Google OAuth não configuradas. Adicione GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET."
        )
    return {"auth_url": auth_url, "redirect_uri": redirect_uri}


@router.get("/auth/callback")
def oauth_callback(code: str, request: Request):
    redirect_uri = os.getenv("GDRIVE_REDIRECT_URI")
    if not redirect_uri:
        base_url = str(request.base_url).rstrip("/")
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            base_url = f"{forwarded_proto}://{request.url.netloc}"
        redirect_uri = f"{base_url}/api/gdrive/auth/callback"
    try:
        handle_oauth_callback(code, redirect_uri)
        return RedirectResponse(url="/?gdrive_success=1")
    except Exception as e:
        return RedirectResponse(url=f"/?gdrive_error={str(e)}")


@router.post("/disconnect")
def disconnect_account(user: str = Depends(require_auth)):
    disconnect_gdrive()
    return {"message": "Conta do Google desconectada com sucesso."}


@router.post("/sync")
def sync_gdrive(db: Session = Depends(get_db), user: str = Depends(require_auth)):
    config = get_stored_config()
    folder_id = config.get("folder_id")
    if not folder_id:
        raise HTTPException(
            status_code=400,
            detail="ID da pasta do Google Drive não configurado. Por favor, informe o ID ou link da pasta."
        )

    try:
        result = sync_drive_receipts(folder_id, db)
        return {
            "message": f"Sincronização concluída: {result['imported']} novo(s) comprovante(s) importado(s).",
            **result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao sincronizar com Google Drive: {str(e)}")
