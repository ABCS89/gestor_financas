import os
import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.models import Receipt

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def save_receipt_file(file: UploadFile, db: Session, notes: str = None) -> Receipt:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de arquivo não suportado ({ext}). Envie imagens (JPG, PNG, WEBP) ou PDF."
        )

    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Arquivo muito grande. O limite máximo é de 10 MB."
        )

    # Gera nome único para salvar no disco
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    destination_path = UPLOAD_DIR / unique_filename

    with open(destination_path, "wb") as f:
        f.write(content)

    receipt = Receipt(
        filename=unique_filename,
        original_filename=file.filename or "comprovante",
        content_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        notes=notes
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return receipt


def get_receipt_filepath(filename: str) -> Path:
    # Previne path traversal
    safe_name = Path(filename).name
    filepath = UPLOAD_DIR / safe_name
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Comprovante não encontrado no servidor.")
    return filepath
