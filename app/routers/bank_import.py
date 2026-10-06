from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Transaction
from app.schemas import BankImportPreview, BankTransactionParsed
from app.services.bank_parser import parse_ofx, parse_csv

router = APIRouter(prefix="/api/bank", tags=["Importação Bancária"])


@router.post("/preview", response_model=BankImportPreview)
async def preview_bank_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    ext = Path(file.filename or "").suffix.lower()
    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    try:
        if ext == ".ofx":
            result = parse_ofx(content, db)
        elif ext == ".csv":
            result = parse_csv(content, db)
        else:
            raise HTTPException(
                status_code=400,
                detail="Formato inválido. Por favor envie um arquivo com extensão .OFX ou .CSV do seu banco."
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar extrato bancário: {str(e)}")

    return BankImportPreview(
        filename=file.filename or "extrato",
        bank_name=result.get("bank_name"),
        account_id=result.get("account_id"),
        transactions=result["transactions"],
        total_income=result["total_income"],
        total_expense=result["total_expense"],
        total_count=result["total_count"],
        duplicates_count=result["duplicates_count"]
    )


class ConfirmImportRequest(BaseModel):
    transactions: List[BankTransactionParsed]


@router.post("/confirm")
def confirm_bank_import(
    request: ConfirmImportRequest,
    db: Session = Depends(get_db)
):
    inserted_count = 0
    skipped_count = 0

    for item in request.transactions:
        # Pular se já existe no banco
        if item.external_id:
            exists = db.query(Transaction).filter(Transaction.external_id == item.external_id).first()
            if exists:
                skipped_count += 1
                continue

        tx = Transaction(
            description=item.description,
            amount=abs(item.amount),
            type=item.type,
            date=item.date,
            category_id=item.suggested_category_id,
            source="ofx" if "FITID" in (item.external_id or "") else "banco",
            external_id=item.external_id
        )
        db.add(tx)
        inserted_count += 1

    db.commit()
    return {
        "message": f"Importação concluída: {inserted_count} transações adicionadas, {skipped_count} duplicadas ignoradas.",
        "inserted_count": inserted_count,
        "skipped_count": skipped_count
    }
