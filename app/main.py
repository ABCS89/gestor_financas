import os
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.routers import categories, receipts, transactions, bank_import, analytics, gdrive
from app.routers.categories import seed_categories

# Criar tabelas no banco de dados SQLite
Base.metadata.create_all(bind=engine)

# Criar pasta de uploads se não existir
Path("uploads").mkdir(parents=True, exist_ok=True)
Path("static").mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Gestor de Finanças Pessoais",
    description="Aplicativo moderno de controle financeiro com extrato bancário e comprovantes",
    version="1.0.0"
)

# CORS liberado para testes e acesso local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.auth import router as auth_router, require_auth

# Incluir rotas de autenticação (públicas)
app.include_router(auth_router)

# Incluir rotas protegidas da API
app.include_router(categories.router, dependencies=[Depends(require_auth)])
app.include_router(receipts.router, dependencies=[Depends(require_auth)])
app.include_router(transactions.router, dependencies=[Depends(require_auth)])
app.include_router(bank_import.router, dependencies=[Depends(require_auth)])
app.include_router(analytics.router, dependencies=[Depends(require_auth)])
app.include_router(gdrive.router, dependencies=[Depends(require_auth)])


# Inicialização: alimentar categorias padrão
@app.on_event("startup")
def on_startup():
    db: Session = next(get_db())
    seed_categories(db)
    db.close()


# Montar arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")


# Servir a página principal do aplicativo
@app.get("/")
def serve_home():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
