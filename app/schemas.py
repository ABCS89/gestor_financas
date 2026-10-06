from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# --- Categorias ---
class CategoryBase(BaseModel):
    name: str
    type: str  # 'expense' ou 'income'
    icon: Optional[str] = "tag"
    color: Optional[str] = "#6b7280"


class CategoryCreate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    id: int

    class Config:
        from_attributes = True


# --- Contas ---
class AccountBase(BaseModel):
    name: str
    account_type: Optional[str] = "corrente"
    initial_balance: Optional[float] = 0.0


class AccountCreate(AccountBase):
    pass


class AccountOut(AccountBase):
    id: int

    class Config:
        from_attributes = True


# --- Comprovantes ---
class ReceiptOut(BaseModel):
    id: int
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    uploaded_at: datetime
    notes: Optional[str] = None
    url: Optional[str] = None

    class Config:
        from_attributes = True


# --- Transações ---
class TransactionBase(BaseModel):
    description: str
    amount: float = Field(gt=0, description="Valor sempre positivo")
    type: str  # 'expense' ou 'income'
    date: date
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    notes: Optional[str] = None


class TransactionCreate(TransactionBase):
    receipt_id: Optional[int] = None
    source: Optional[str] = "manual"
    external_id: Optional[str] = None


class TransactionUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = None
    type: Optional[str] = None
    date: Optional[date] = None
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    receipt_id: Optional[int] = None
    notes: Optional[str] = None


class TransactionOut(TransactionBase):
    id: int
    receipt_id: Optional[int] = None
    source: str
    external_id: Optional[str] = None
    created_at: datetime
    category: Optional[CategoryOut] = None
    receipt: Optional[ReceiptOut] = None

    class Config:
        from_attributes = True


# --- Importação Bancária ---
class BankTransactionParsed(BaseModel):
    date: date
    amount: float
    type: str  # 'expense' ou 'income'
    description: str
    external_id: Optional[str] = None
    suggested_category_id: Optional[int] = None
    suggested_category_name: Optional[str] = None
    is_duplicate: bool = False


class BankImportPreview(BaseModel):
    filename: str
    bank_name: Optional[str] = None
    account_id: Optional[str] = None
    transactions: List[BankTransactionParsed]
    total_income: float
    total_expense: float
    total_count: int
    duplicates_count: int
