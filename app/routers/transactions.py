import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Transaction, Category, Receipt
from app.schemas import TransactionOut, TransactionCreate, TransactionUpdate
from app.services.receipt_service import save_receipt_file

router = APIRouter(prefix="/api/transactions", tags=["Transações"])


@router.get("", response_model=List[TransactionOut])
def get_transactions(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    type: Optional[str] = Query(None, pattern="^(income|expense)$"),
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(Transaction).options(
        joinedload(Transaction.category),
        joinedload(Transaction.receipt)
    )

    if month and year:
        start_date = datetime.date(year, month, 1)
        if month == 12:
            end_date = datetime.date(year + 1, 1, 1)
        else:
            end_date = datetime.date(year, month + 1, 1)
        query = query.filter(Transaction.date >= start_date, Transaction.date < end_date)
    elif year:
        query = query.filter(Transaction.date >= datetime.date(year, 1, 1), Transaction.date <= datetime.date(year, 12, 31))

    if type:
        query = query.filter(Transaction.type == type)

    if category_id:
        query = query.filter(Transaction.category_id == category_id)

    if search:
        query = query.filter(Transaction.description.ilike(f"%{search}%"))

    return query.order_by(Transaction.date.desc(), Transaction.id.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=TransactionOut)
def create_transaction_json(tx: TransactionCreate, db: Session = Depends(get_db)):
    db_tx = Transaction(**tx.model_dump())
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx


@router.post("/with-receipt", response_model=TransactionOut)
async def create_transaction_with_receipt(
    description: str = Form(...),
    amount: float = Form(...),
    type: str = Form(...),
    date_str: str = Form(..., alias="date"),
    category_id: Optional[int] = Form(None),
    notes: Optional[str] = Form(None),
    receipt_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    try:
        tx_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida. Use o formato AAAA-MM-DD.")

    receipt_id = None
    if receipt_file and receipt_file.filename:
        receipt = await save_receipt_file(receipt_file, db, notes=f"Comprovante de {description}")
        receipt_id = receipt.id

    db_tx = Transaction(
        description=description.strip(),
        amount=abs(amount),
        type=type,
        date=tx_date,
        category_id=category_id,
        receipt_id=receipt_id,
        notes=notes,
        source="manual"
    )
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx


@router.put("/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: int, tx_data: TransactionUpdate, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    for field, val in tx_data.model_dump(exclude_unset=True).items():
        setattr(tx, field, val)

    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/{tx_id}")
def delete_transaction(tx_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    db.delete(tx)
    db.commit()
    return {"message": "Transação removida com sucesso"}
