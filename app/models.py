import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # 'expense' ou 'income'
    icon = Column(String(50), default="tag")
    color = Column(String(20), default="#6b7280")

    transactions = relationship("Transaction", back_populates="category")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    account_type = Column(String(50), default="corrente")  # corrente, poupanca, cartao, dinheiro
    initial_balance = Column(Float, default=0.0)

    transactions = relationship("Transaction", back_populates="account")


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(Text, nullable=True)
    drive_file_id = Column(String(100), nullable=True, unique=True, index=True)
    drive_web_url = Column(String(500), nullable=True)

    transaction = relationship("Transaction", back_populates="receipt", uselist=False)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String(20), nullable=False)  # 'expense' ou 'income'
    date = Column(Date, nullable=False, index=True)
    
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=True, unique=True)
    
    source = Column(String(50), default="manual")  # 'manual', 'ofx', 'csv'
    external_id = Column(String(255), nullable=True, index=True)  # FITID do OFX ou identificador único
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    category = relationship("Category", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")
    receipt = relationship("Receipt", back_populates="transaction")
