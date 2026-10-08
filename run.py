import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("=" * 60)
    print(f"Iniciando Gestor de Finanças Pessoais na porta {port}...")
    print(f"Acesse no navegador: http://localhost:{port}")
    print("=" * 60)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
