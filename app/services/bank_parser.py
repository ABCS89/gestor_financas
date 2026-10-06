import io
import csv
import hashlib
from datetime import datetime, date
from typing import List, Tuple, Dict, Any, Optional
from ofxparse import OfxParser
from sqlalchemy.orm import Session
from app.models import Transaction, Category


# Dicionário de palavras-chave para auto-categorização inteligente
KEYWORD_CATEGORY_MAP = {
    "Alimentação": [
        "ifood", "mercado", "supermercado", "carrefour", "pao de acucar", "assai", "atacadista",
        "padaria", "restaurante", "lanchonete", "mcdonald", "burger king", "subway", "bar",
        "cafe", "churrascaria", "pizzaria", "hortifruti", "acougue", "rappi"
    ],
    "Transporte": [
        "uber", "99app", "99 tecnologia", "posto", "combustivel", "gasolina", "etanol",
        "ipva", "estacionamento", "estapar", "pedagio", "sem parar", "veloe", "metro", "onibus"
    ],
    "Moradia": [
        "aluguel", "condominio", "enel", "cemig", "cpfl", "sabesp", "copasa", "sanepar",
        "gas", "comgas", "energia", "luz", "agua", "internet", "claro", "vivo", "tim", "oi"
    ],
    "Lazer": [
        "netflix", "spotify", "amazon prime", "disney", "hbo", "cinema", "cinemark",
        "steam", "playstation", "xbox", "ingresso", "show", "teatro", "jogos"
    ],
    "Saúde": [
        "farmacia", "droga raia", "drogasil", "pague menos", "panvel", "drogaria",
        "consulta", "medico", "dentista", "laboratorio", "exame", "hospital", "otica"
    ],
    "Educação": [
        "udemy", "alura", "curso", "faculdade", "escola", "livraria", "livro", "mensalidade"
    ],
    "Compras": [
        "amazon", "shopee", "mercado livre", "magalu", "magazine luiza", "aliexpress",
        "shein", "zara", "renner", "riachuelo", "loja"
    ],
    "Salário & Renda": [
        "salario", "remuneracao", "provento", "ted recebida", "pix recebido", "rendimento",
        "dividendo", "folha", "adve", "honorarios"
    ],
}


def suggest_category(description: str, tx_type: str, categories: List[Category]) -> Optional[Category]:
    desc_lower = description.lower()
    
    # Busca por palavras-chave
    for cat_name, keywords in KEYWORD_CATEGORY_MAP.items():
        for kw in keywords:
            if kw in desc_lower:
                # Procura a categoria no banco pelo nome
                for cat in categories:
                    if cat.name.lower() == cat_name.lower():
                        return cat
    
    # Se não achou por palavra-chave, sugere a categoria padrão pelo tipo
    for cat in categories:
        if tx_type == "income" and cat.type == "income" and "outros" in cat.name.lower():
            return cat
        if tx_type == "expense" and cat.type == "expense" and "outros" in cat.name.lower():
            return cat
            
    return None


def generate_tx_hash(tx_date: date, amount: float, description: str) -> str:
    raw = f"{tx_date.isoformat()}_{round(amount, 2)}_{description.strip().lower()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def check_is_duplicate(db: Session, external_id: str, tx_date: date, amount: float, description: str) -> bool:
    if external_id:
        existing = db.query(Transaction).filter(Transaction.external_id == external_id).first()
        if existing:
            return True
            
    # Checagem secundária por data, valor e descrição similar
    similar = db.query(Transaction).filter(
        Transaction.date == tx_date,
        Transaction.amount == amount,
        Transaction.description == description.strip()
    ).first()
    return similar is not None


def parse_ofx(file_content: bytes, db: Session) -> Dict[str, Any]:
    categories = db.query(Category).all()
    try:
        ofx = OfxParser.parse(io.BytesIO(file_content))
    except Exception as e:
        # Tentar decodificar com latin1 ou utf-8 se falhar
        try:
            text = file_content.decode("latin1", errors="replace")
            ofx = OfxParser.parse(io.StringIO(text))
        except Exception as inner_e:
            raise ValueError(f"Não foi possível processar o arquivo OFX: {str(inner_e)}")

    account = ofx.account
    bank_name = getattr(account, "institution", None) or getattr(account, "routing_number", None) or "Banco"
    account_id = getattr(account, "number", None) or ""

    parsed_transactions = []
    total_income = 0.0
    total_expense = 0.0
    duplicates_count = 0

    if account and account.statement:
        for tx in account.statement.transactions:
            raw_amount = float(tx.amount)
            tx_type = "income" if raw_amount > 0 else "expense"
            amount = abs(raw_amount)
            tx_date = tx.date.date() if isinstance(tx.date, datetime) else tx.date
            description = (tx.memo or tx.payee or "Transação bancária").strip()
            
            external_id = getattr(tx, "id", None) or generate_tx_hash(tx_date, amount, description)
            is_dup = check_is_duplicate(db, external_id, tx_date, amount, description)
            if is_dup:
                duplicates_count += 1

            if tx_type == "income":
                total_income += amount
            else:
                total_expense += amount

            sug_cat = suggest_category(description, tx_type, categories)

            parsed_transactions.append({
                "date": tx_date,
                "amount": amount,
                "type": tx_type,
                "description": description,
                "external_id": external_id,
                "suggested_category_id": sug_cat.id if sug_cat else None,
                "suggested_category_name": sug_cat.name if sug_cat else "Sem categoria",
                "is_duplicate": is_dup
            })

    # Ordenar pelas datas mais recentes
    parsed_transactions.sort(key=lambda x: x["date"], reverse=True)

    return {
        "bank_name": str(bank_name),
        "account_id": str(account_id),
        "transactions": parsed_transactions,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "total_count": len(parsed_transactions),
        "duplicates_count": duplicates_count
    }


def parse_csv(file_content: bytes, db: Session) -> Dict[str, Any]:
    categories = db.query(Category).all()
    # Tentar decodificar UTF-8 ou Latin-1
    text = ""
    for enc in ["utf-8-sig", "utf-8", "latin-1"]:
        try:
            text = file_content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        raise ValueError("Codificação de arquivo CSV inválida.")

    # Detecção de delimitador (, ou ;)
    first_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if ";" in first_line else ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        raise ValueError("O arquivo CSV está vazio.")

    header = [h.strip().lower() for h in rows[0]]
    # Encontrar colunas de data, valor e descrição
    date_idx = -1
    amount_idx = -1
    desc_idx = -1

    for i, col in enumerate(header):
        if any(term in col for term in ["data", "date"]):
            date_idx = i
        elif any(term in col for term in ["valor", "amount", "valor (r$)"]):
            amount_idx = i
        elif any(term in col for term in ["descri", "hist", "memo", "title", "estabelecimento"]):
            desc_idx = i

    if date_idx == -1 or amount_idx == -1:
        raise ValueError("Cabeçalhos do CSV não reconhecidos (necessário conter 'Data' e 'Valor').")
    if desc_idx == -1:
        # Pega a primeira coluna que não for data nem valor
        for i in range(len(header)):
            if i not in [date_idx, amount_idx]:
                desc_idx = i
                break

    parsed_transactions = []
    total_income = 0.0
    total_expense = 0.0
    duplicates_count = 0

    for row in rows[1:]:
        if not row or len(row) <= max(date_idx, amount_idx):
            continue
        date_str = row[date_idx].strip()
        amount_str = row[amount_idx].strip()
        description = row[desc_idx].strip() if desc_idx != -1 and desc_idx < len(row) else "Transação"

        if not date_str or not amount_str:
            continue

        # Parse data (DD/MM/YYYY, YYYY-MM-DD, etc.)
        parsed_date = None
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"]:
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                pass
        if not parsed_date:
            continue

        # Parse valor (tratando vírgula e ponto brasileiro: ex " -1.250,50 " ou "-1250.50")
        clean_amount_str = amount_str.replace("R$", "").replace(" ", "")
        if "," in clean_amount_str and "." in clean_amount_str:
            clean_amount_str = clean_amount_str.replace(".", "").replace(",", ".")
        elif "," in clean_amount_str:
            clean_amount_str = clean_amount_str.replace(",", ".")
        try:
            raw_amount = float(clean_amount_str)
        except ValueError:
            continue

        tx_type = "income" if raw_amount > 0 else "expense"
        amount = abs(raw_amount)

        external_id = generate_tx_hash(parsed_date, amount, description)
        is_dup = check_is_duplicate(db, external_id, parsed_date, amount, description)
        if is_dup:
            duplicates_count += 1

        if tx_type == "income":
            total_income += amount
        else:
            total_expense += amount

        sug_cat = suggest_category(description, tx_type, categories)

        parsed_transactions.append({
            "date": parsed_date,
            "amount": amount,
            "type": tx_type,
            "description": description,
            "external_id": external_id,
            "suggested_category_id": sug_cat.id if sug_cat else None,
            "suggested_category_name": sug_cat.name if sug_cat else "Sem categoria",
            "is_duplicate": is_dup
        })

    parsed_transactions.sort(key=lambda x: x["date"], reverse=True)

    return {
        "bank_name": "Extrato CSV",
        "account_id": "",
        "transactions": parsed_transactions,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "total_count": len(parsed_transactions),
        "duplicates_count": duplicates_count
    }
