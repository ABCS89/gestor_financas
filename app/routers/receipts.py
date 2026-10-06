from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Receipt, Transaction
from app.schemas import ReceiptOut
from app.services.receipt_service import save_receipt_file, get_receipt_filepath

router = APIRouter(prefix="/api/receipts", tags=["Comprovantes"])


@router.post("/upload", response_model=ReceiptOut)
async def upload_receipt(
    file: UploadFile = File(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    receipt = await save_receipt_file(file, db, notes=notes)
    return ReceiptOut(
        id=receipt.id,
        filename=receipt.filename,
        original_filename=receipt.original_filename,
        content_type=receipt.content_type,
        file_size=receipt.file_size,
        uploaded_at=receipt.uploaded_at,
        notes=receipt.notes,
        url=f"/api/receipts/view/{receipt.filename}"
    )


@router.get("", response_model=List[dict])
def list_receipts(db: Session = Depends(get_db)):
    receipts = db.query(Receipt).order_by(Receipt.uploaded_at.desc()).all()
    results = []
    for r in receipts:
        tx_info = None
        if r.transaction:
            tx_info = {
                "id": r.transaction.id,
                "description": r.transaction.description,
                "amount": r.transaction.amount,
                "date": r.transaction.date.isoformat(),
                "type": r.transaction.type
            }
        results.append({
            "id": r.id,
            "filename": r.filename,
            "original_filename": r.original_filename,
            "content_type": r.content_type,
            "file_size": r.file_size,
            "uploaded_at": r.uploaded_at.isoformat(),
            "notes": r.notes,
            "url": f"/api/receipts/view/{r.filename}",
            "transaction": tx_info
        })
    return results


@router.get("/view/{filename}")
def view_receipt(filename: str):
    filepath = get_receipt_filepath(filename)
    # Define Content-Type apropriado para visualização embutida no navegador
    return FileResponse(
        path=filepath,
        media_type=None,
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )


@router.delete("/{receipt_id}")
def delete_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Comprovante não encontrado")
    
    # Desvincular transação se houver
    if receipt.transaction:
        receipt.transaction.receipt_id = None
        db.add(receipt.transaction)

    # Remover do disco
    try:
        filepath = get_receipt_filepath(receipt.filename)
        if filepath.exists():
            filepath.unlink()
    except Exception:
        pass

    db.delete(receipt)
    db.commit()
    return {"message": "Comprovante excluído com sucesso"}
