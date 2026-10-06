from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.gdrive_service import (
    test_drive_connection,
    get_stored_config,
    save_stored_config,
    sync_drive_receipts
)

router = APIRouter(prefix="/api/gdrive", tags=["Google Drive"])


class GDriveConfigPayload(BaseModel):
    folder_id: str


@router.get("/status")
def get_gdrive_status():
    status = test_drive_connection()
    config = get_stored_config()
    status["folder_id"] = config.get("folder_id", "")
    return status


@router.post("/config")
def set_gdrive_config(payload: GDriveConfigPayload):
    config = get_stored_config()
    # Limpa a URL se o usuário colou o link completo da pasta em vez de apenas o ID
    folder_id = payload.folder_id.strip()
    if "folders/" in folder_id:
        folder_id = folder_id.split("folders/")[-1].split("?")[0]
    
    config["folder_id"] = folder_id
    save_stored_config(config)
    return {"message": "Configuração da pasta salva com sucesso!", "folder_id": folder_id}


@router.post("/sync")
def sync_gdrive(db: Session = Depends(get_db)):
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
