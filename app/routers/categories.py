from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Category
from app.schemas import CategoryOut, CategoryCreate

router = APIRouter(prefix="/api/categories", tags=["Categorias"])

DEFAULT_CATEGORIES = [
    # Despesas
    {"name": "Alimentação", "type": "expense", "icon": "utensils", "color": "#f97316"},
    {"name": "Moradia & Contas", "type": "expense", "icon": "home", "color": "#3b82f6"},
    {"name": "Transporte", "type": "expense", "icon": "car", "color": "#eab308"},
    {"name": "Saúde", "type": "expense", "icon": "heart-pulse", "color": "#ef4444"},
    {"name": "Lazer & Streaming", "type": "expense", "icon": "film", "color": "#a855f7"},
    {"name": "Compras & Vestuário", "type": "expense", "icon": "shopping-bag", "color": "#ec4899"},
    {"name": "Educação", "type": "expense", "icon": "graduation-cap", "color": "#14b8a6"},
    {"name": "Outras Despesas", "type": "expense", "icon": "tag", "color": "#64748b"},
    # Receitas
    {"name": "Salário & Renda", "type": "income", "icon": "briefcase", "color": "#10b981"},
    {"name": "Investimentos", "type": "income", "icon": "trending-up", "color": "#06b6d4"},
    {"name": "Freelance / Bicos", "type": "income", "icon": "laptop", "color": "#8b5cf6"},
    {"name": "Outras Receitas", "type": "income", "icon": "plus-circle", "color": "#22c55e"},
]


def seed_categories(db: Session):
    count = db.query(Category).count()
    if count == 0:
        for cat_data in DEFAULT_CATEGORIES:
            db.add(Category(**cat_data))
        db.commit()


@router.get("", response_model=List[CategoryOut])
def get_categories(type: str = None, db: Session = Depends(get_db)):
    seed_categories(db)
    query = db.query(Category)
    if type:
        query = query.filter(Category.type == type)
    return query.order_by(Category.name).all()


@router.post("", response_model=CategoryOut)
def create_category(cat: CategoryCreate, db: Session = Depends(get_db)):
    new_cat = Category(**cat.model_dump())
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat
