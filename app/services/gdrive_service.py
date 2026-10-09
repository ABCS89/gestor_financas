import os
import io
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from sqlalchemy.orm import Session
from app.models import Receipt
from app.services.receipt_service import UPLOAD_DIR

GDRIVE_SETTINGS_FILE = Path("gdrive_config.json")
SERVICE_ACCOUNT_FILE = Path("service_account.json")
TOKEN_FILE = Path("token.json")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def get_stored_config() -> Dict[str, Any]:
    if GDRIVE_SETTINGS_FILE.exists():
        try:
            with open(GDRIVE_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"folder_id": os.getenv("GDRIVE_FOLDER_ID", "")}


def save_stored_config(config: Dict[str, Any]):
    with open(GDRIVE_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_drive_credentials():
    # 1. Variável de ambiente com JSON do Service Account (para Render / Produção)
    env_json = os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON")
    if env_json:
        try:
            info = json.loads(env_json)
            return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as e:
            print(f"Erro ao carregar GDRIVE_SERVICE_ACCOUNT_JSON: {e}")

    # 2. Arquivo service_account.json local
    if SERVICE_ACCOUNT_FILE.exists():
        try:
            return service_account.Credentials.from_service_account_file(
                str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
            )
        except Exception as e:
            print(f"Erro ao carregar service_account.json: {e}")

    # 3. Arquivo token.json (se OAuth2 foi usado)
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), scopes=SCOPES)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            return creds
        except Exception as e:
            print(f"Erro ao carregar token.json: {e}")

    return None


def get_oauth_client_config() -> Optional[Dict[str, Any]]:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if client_id and client_secret:
        return {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
            }
        }
    creds_file = Path("credentials.json")
    if creds_file.exists():
        try:
            with open(creds_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


VERIFIER_TEMP_FILE = Path(".oauth_verifier.tmp")


def get_oauth_authorization_url(redirect_uri: str) -> Tuple[Optional[str], Optional[str]]:
    from string import ascii_letters, digits
    from random import SystemRandom
    from google_auth_oauthlib.flow import Flow

    client_config = get_oauth_client_config()
    if not client_config:
        return None, None
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    # Gera explicitamente o code_verifier ANTES para o Flow usar no hash e passar no state
    chars = ascii_letters + digits + "-._~"
    rnd = SystemRandom()
    code_verifier = "".join([rnd.choice(chars) for _ in range(0, 128)])
    flow.code_verifier = code_verifier

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account consent",
        state=code_verifier
    )

    try:
        with open(VERIFIER_TEMP_FILE, "w", encoding="utf-8") as f:
            f.write(code_verifier)
    except Exception:
        pass

    return auth_url, code_verifier


def handle_oauth_callback(code: str, redirect_uri: str, code_verifier: Optional[str] = None):
    from google_auth_oauthlib.flow import Flow
    client_config = get_oauth_client_config()
    if not client_config:
        raise ValueError("Configuração do cliente OAuth não encontrada.")

    # Se não veio via parâmetro, tenta ler do arquivo temporário
    if not code_verifier and VERIFIER_TEMP_FILE.exists():
        try:
            with open(VERIFIER_TEMP_FILE, "r", encoding="utf-8") as f:
                code_verifier = f.read().strip()
        except Exception:
            pass

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    if code_verifier:
        flow.code_verifier = code_verifier
        flow.fetch_token(code=code, code_verifier=code_verifier)
    else:
        flow.fetch_token(code=code)

    creds = flow.credentials
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    # Limpa arquivo temporário
    if VERIFIER_TEMP_FILE.exists():
        try:
            VERIFIER_TEMP_FILE.unlink()
        except Exception:
            pass

    return creds


def disconnect_gdrive():
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    return True


def get_drive_service():
    creds = get_drive_credentials()
    if not creds:
        return None
    return build("drive", "v3", credentials=creds)


def test_drive_connection() -> Dict[str, Any]:
    creds = get_drive_credentials()
    if not creds:
        return {
            "connected": False,
            "message": "Nenhuma credencial do Google Drive configurada. Adicione o arquivo service_account.json ou a variável GDRIVE_SERVICE_ACCOUNT_JSON."
        }
    try:
        service = build("drive", "v3", credentials=creds)
        about = service.about().get(fields="user, storageQuota").execute()
        user_info = about.get("user", {})
        return {
            "connected": True,
            "user_email": getattr(creds, "service_account_email", None) or user_info.get("emailAddress", "Conectado"),
            "display_name": user_info.get("displayName", "Conta Google"),
            "is_service_account": hasattr(creds, "service_account_email")
        }
    except Exception as e:
        return {
            "connected": False,
            "message": f"Falha ao autenticar no Google Drive: {str(e)}"
        }


def list_files_in_folder(service, folder_id: str) -> List[Dict[str, Any]]:
    all_files = []
    folders_to_scan = [folder_id]
    visited_folders = set()

    # Varre a pasta principal e todas as subpastas recursivamente
    while folders_to_scan:
        current_folder = folders_to_scan.pop(0)
        if current_folder in visited_folders:
            continue
        visited_folders.add(current_folder)

        # 1. Busca arquivos de imagens e PDFs nesta pasta
        file_query = (
            f"'{current_folder}' in parents and trashed = false and "
            "(mimeType contains 'image/' or mimeType = 'application/pdf')"
        )
        page_token = None
        while True:
            try:
                results = service.files().list(
                    q=file_query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name, mimeType, size, webViewLink, createdTime)",
                    pageToken=page_token
                ).execute()
                all_files.extend(results.get("files", []))
                page_token = results.get("nextPageToken")
                if not page_token:
                    break
            except Exception as e:
                print(f"Erro ao listar arquivos na pasta {current_folder}: {e}")
                break

        # 2. Busca subpastas dentro desta pasta para explorar
        try:
            folder_query = (
                f"'{current_folder}' in parents and trashed = false and "
                "mimeType = 'application/vnd.google-apps.folder'"
            )
            subfolders = service.files().list(
                q=folder_query,
                pageSize=100,
                fields="files(id, name)"
            ).execute()
            for sub in subfolders.get("files", []):
                if sub["id"] not in visited_folders:
                    folders_to_scan.append(sub["id"])
        except Exception as e:
            print(f"Erro ao listar subpastas: {e}")

    return all_files


def sync_drive_receipts(folder_id: str, db: Session) -> Dict[str, Any]:
    service = get_drive_service()
    if not service:
        raise ValueError("Google Drive não está autenticado. Configure as credenciais primeiro.")

    if not folder_id:
        raise ValueError("ID da pasta do Google Drive não informado.")

    files = list_files_in_folder(service, folder_id)
    imported_count = 0
    already_imported_count = 0

    for f in files:
        file_id = f["id"]
        file_name = f["name"]
        mime_type = f.get("mimeType", "application/octet-stream")
        web_link = f.get("webViewLink", "")

        # Verifica se já foi importado
        existing = db.query(Receipt).filter(Receipt.drive_file_id == file_id).first()
        if existing:
            already_imported_count += 1
            continue

        # Baixar conteúdo do arquivo
        ext = Path(file_name).suffix.lower()
        if not ext:
            ext = ".pdf" if "pdf" in mime_type else ".jpg"

        unique_filename = f"drive_{uuid.uuid4().hex[:12]}_{file_id[:8]}{ext}"
        destination = UPLOAD_DIR / unique_filename

        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        file_bytes = fh.getvalue()
        with open(destination, "wb") as out_f:
            out_f.write(file_bytes)

        receipt = Receipt(
            filename=unique_filename,
            original_filename=file_name,
            content_type=mime_type,
            file_size=len(file_bytes),
            notes=f"Sincronizado automaticamente do Google Drive",
            drive_file_id=file_id,
            drive_web_url=web_link
        )
        db.add(receipt)
        imported_count += 1

    db.commit()

    return {
        "total_in_drive": len(files),
        "imported": imported_count,
        "already_synced": already_imported_count
    }
