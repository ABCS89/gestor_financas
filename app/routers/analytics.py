import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Transaction, Category

router = APIRouter(prefix="/api/analytics", tags=["Relatórios e Dashboard"])


@router.get("/summary")
def get_monthly_summary(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db)
):
    today = datetime.date.today()
    target_month = month or today.month
    target_year = year or today.year

    start_date = datetime.date(target_year, target_month, 1)
    if target_month == 12:
        end_date = datetime.date(target_year + 1, 1, 1)
    else:
        end_date = datetime.date(target_year, target_month + 1, 1)

    transactions = db.query(Transaction).filter(
        Transaction.date >= start_date,
        Transaction.date < end_date
    ).all()

    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expense = sum(t.amount for t in transactions if t.type == "expense")
    balance = total_income - total_expense

    # Gastos por categoria
    category_map = {}
    for t in transactions:
        if t.type == "expense":
            cat_name = t.category.name if t.category else "Sem Categoria"
            cat_color = t.category.color if t.category else "#94a3b8"
            cat_icon = t.category.icon if t.category else "tag"

            if cat_name not in category_map:
                category_map[cat_name] = {
                    "name": cat_name,
                    "color": cat_color,
                    "icon": cat_icon,
                    "total": 0.0
                }
            category_map[cat_name]["total"] += t.amount

    category_breakdown = list(category_map.values())
    for item in category_breakdown:
        item["total"] = round(item["total"], 2)
        item["percentage"] = round((item["total"] / total_expense * 100), 1) if total_expense > 0 else 0

    category_breakdown.sort(key=lambda x: x["total"], reverse=True)

    # Total de comprovantes anexados no mês
    receipts_count = sum(1 for t in transactions if t.receipt_id is not None)

    return {
        "month": target_month,
        "year": target_year,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "balance": round(balance, 2),
        "transaction_count": len(transactions),
        "receipts_count": receipts_count,
        "category_breakdown": category_breakdown
    }
