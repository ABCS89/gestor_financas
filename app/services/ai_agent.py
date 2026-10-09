import os
import json
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import Receipt, Transaction, Category
from app.services.receipt_service import get_receipt_filepath

# Modelos padrão do Gemini (suporta Flash ou Pro)
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


class ReceiptAnalysisResult(BaseModel):
    tipo_documento: str = Field(description="Tipo: comprovante_pix, comprovante_boleto, boleto, fatura_energia, cupom_fiscal, outro")
    estabelecimento: str = Field(description="Nome da empresa ou favorecido, ex: CPFL Paulista, Drogasil, Santander")
    descricao: str = Field(description="Descrição clara do gasto, ex: CPFL Paulista - Conta de Energia")
    valor: float = Field(description="Valor numérico pago ou a pagar em reais")
    data: str = Field(description="Data da transação ou vencimento no formato AAAA-MM-DD")
    categoria_sugerida: str = Field(description="Melhor categoria dentre as disponíveis")
    codigo_identificacao: Optional[str] = Field(default=None, description="Código de autenticação, ID Pix ou código de barras")
    observacoes: Optional[str] = Field(default=None, description="Observações relevantes encontradas no documento")


def get_clean_api_key() -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        key_file = Path("gemini_key.txt")
        if key_file.exists():
            try:
                api_key = key_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass

    if not api_key:
        return None

    api_key = api_key.strip().strip("'\"")
    if api_key.lower().startswith("bearer "):
        api_key = api_key[7:].strip()

    return api_key


def get_gemini_client():
    api_key = get_clean_api_key()
    if not api_key:
        return None

    from google import genai
    from google.genai import types
    http_opts = types.HttpOptions(
        headers={"x-goog-api-key": api_key}
    )
    return genai.Client(api_key=api_key, http_options=http_opts)


def call_gemini_rest_direct(
    model_name: str, file_bytes: bytes, mime_type: str, prompt: str, api_key: str
) -> ReceiptAnalysisResult:
    import base64
    import urllib.request
    import urllib.error

    b64_data = base64.b64encode(file_bytes).decode("utf-8")
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_data
                        }
                    },
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1
        }
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp_body = resp.read().decode("utf-8")
            resp_json = json.loads(resp_body)
            candidates = resp_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    raw_text = parts[0].get("text", "{}")
                    parsed = json.loads(raw_text)
                    return ReceiptAnalysisResult(**parsed)
            raise ValueError("Resposta vazia da API do Gemini")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise ValueError(f"HTTP {e.code}: {err_msg}")
    except Exception as e:
        raise ValueError(str(e))


def analyze_receipt_document(receipt: Receipt, categories: List[Category]) -> ReceiptAnalysisResult:
    api_key = get_clean_api_key()
    if not api_key:
        raise ValueError(
            "Chave de API do Gemini não configurada. Defina a variável de ambiente GEMINI_API_KEY no Render."
        )

    # Validações preventivas de formato de chave
    if api_key.startswith("ya29."):
        raise ValueError(
            "A chave informada em GEMINI_API_KEY no Render começa com 'ya29.', que é um token temporário OAuth do Google, e não uma Chave de API do Gemini. Por favor, acesse https://aistudio.google.com/apikey com a sua conta Google e clique em 'Create API key' para gerar a chave correta."
        )
    if api_key.startswith("GOCSPX-"):
        raise ValueError(
            "A chave informada em GEMINI_API_KEY é um Client Secret do OAuth. Para o Agente de IA, é necessária uma Chave de API gerada no Google AI Studio (https://aistudio.google.com/apikey)."
        )
    if "@" in api_key:
        raise ValueError(
            f"Foi inserido um e-mail ('{api_key}') no campo GEMINI_API_KEY no Render. Para funcionar, gere uma Chave de API no Google AI Studio (https://aistudio.google.com/apikey)."
        )

    filepath = get_receipt_filepath(receipt.filename)
    if not filepath.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {receipt.filename}")

    with open(filepath, "rb") as f:
        file_bytes = f.read()

    # Identificar Content-Type para o Gemini
    mime_type = receipt.content_type or "application/pdf"
    if filepath.suffix.lower() == ".pdf":
        mime_type = "application/pdf"
    elif filepath.suffix.lower() in [".jpg", ".jpeg"]:
        mime_type = "image/jpeg"
    elif filepath.suffix.lower() == ".png":
        mime_type = "image/png"
    elif filepath.suffix.lower() == ".webp":
        mime_type = "image/webp"

    categories_names = [c.name for c in categories]
    categories_prompt = ", ".join(categories_names)

    prompt = f"""
    Você é um agente especialista em finanças pessoais e análise de documentos fiscais e bancários no Brasil.
    Analise com atenção este documento (comprovante de pagamento, comprovante Pix, boleto, fatura ou nota fiscal).

    Categorias disponíveis no aplicativo:
    [{categories_prompt}]

    Extraia com precisão:
    1. tipo_documento: (comprovante_pix, comprovante_boleto, boleto, fatura_energia, cupom_fiscal ou outro)
    2. estabelecimento: Razão social ou nome do favorecido (ex: CPFL Paulista, Enel, Mercado Livre, etc.)
    3. descricao: Título amigável da despesa
    4. valor: Valor monetário em reais (ex: 233.46)
    5. data: Data do pagamento ou emissão (no formato AAAA-MM-DD, ex: 2026-02-04)
    6. categoria_sugerida: Escolha a categoria mais apropriada estritamente da lista de categorias acima.
    7. codigo_identificacao: ID do Pix, autenticação bancária ou linha digitável do boleto, se existir.
    8. observacoes: Informações extras (ex: número da conta, mês de referência).

    Seja estritamente preciso nos valores e datas.
    """

    models_to_try = [DEFAULT_GEMINI_MODEL, "gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    last_err = None

    # Método 1: Tentar via SDK oficial google-genai
    try:
        from google.genai import types
        client = get_gemini_client()
        if client:
            part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
            for model_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[part, prompt],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=ReceiptAnalysisResult,
                            temperature=0.1
                        )
                    )
                    raw_json = response.text
                    data = json.loads(raw_json)
                    return ReceiptAnalysisResult(**data)
                except Exception as e:
                    last_err = e
                    continue
    except Exception as e:
        last_err = e

    # Método 2: Fallback direto via REST (evita interferências de cabeçalho do SDK)
    for model_name in models_to_try:
        try:
            return call_gemini_rest_direct(model_name, file_bytes, mime_type, prompt, api_key)
        except Exception as e:
            last_err = e
            continue

    err_str = str(last_err)
    if "401" in err_str or "UNAUTHENTICATED" in err_str or "ACCESS_TOKEN_TYPE_UNSUPPORTED" in err_str:
        masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else api_key
        raise ValueError(
            f"Erro de autenticação com a API do Gemini (401 UNAUTHENTICATED). A chave configurada '{masked}' não foi aceita pelo Google. Verifique no painel do Render em GEMINI_API_KEY se a chave foi gerada no Google AI Studio (https://aistudio.google.com/apikey) na conta Pro, sem espaços extras."
        )

    raise ValueError(f"Erro ao processar documento com a IA do Gemini: {err_str}")


def process_receipt_with_ai(receipt_id: int, db: Session) -> Dict[str, Any]:
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise ValueError("Comprovante não encontrado")

    categories = db.query(Category).all()
    ai_result = analyze_receipt_document(receipt, categories)

    # Parse da data
    try:
        tx_date = datetime.date.fromisoformat(ai_result.data)
    except Exception:
        tx_date = datetime.date.today()

    # Encontrar categoria correspondente no banco
    matched_cat = None
    for cat in categories:
        if cat.name.lower() == ai_result.categoria_sugerida.lower():
            matched_cat = cat
            break
    if not matched_cat and categories:
        # Padrão: Outras Despesas ou a primeira
        matched_cat = next((c for c in categories if "outras" in c.name.lower() and c.type == "expense"), categories[0])

    # ==========================================
    # CRUZAMENTO DE DADOS & ANTI-DUPLICAÇÃO
    # ==========================================
    # 1. Checa por código de autenticação/identificação se houver
    existing_tx = None
    if ai_result.codigo_identificacao:
        existing_tx = db.query(Transaction).filter(
            Transaction.external_id == ai_result.codigo_identificacao
        ).first()

    # 2. Checa por valor e proximidade de data (+/- 3 dias) e estabelecimento similar
    if not existing_tx:
        start_range = tx_date - datetime.timedelta(days=3)
        end_range = tx_date + datetime.timedelta(days=3)
        candidates = db.query(Transaction).filter(
            Transaction.amount == round(ai_result.valor, 2),
            Transaction.date >= start_range,
            Transaction.date <= end_range
        ).all()

        for c in candidates:
            # Se a descrição contiver o estabelecimento ou vice-versa
            if (ai_result.estabelecimento.lower() in c.description.lower() or 
                c.description.lower() in ai_result.estabelecimento.lower()):
                existing_tx = c
                break

    action_taken = ""
    target_tx = None

    if existing_tx:
        # Cruzamento realizado com sucesso: vincula o comprovante ao gasto existente
        existing_tx.receipt_id = receipt.id
        if not existing_tx.notes:
            existing_tx.notes = f"[IA] Comprovante {receipt.original_filename} vinculado."
        else:
            existing_tx.notes += f" | [IA] Vinculado a {receipt.original_filename}"
        
        target_tx = existing_tx
        action_taken = f"Cruzamento realizado: vinculado à transação existente '{existing_tx.description}' de R$ {existing_tx.amount:.2f}."
    else:
        # Novo gasto detectado: cria o lançamento no extrato
        new_tx = Transaction(
            description=ai_result.descricao or ai_result.estabelecimento,
            amount=abs(ai_result.valor),
            type="expense",
            date=tx_date,
            category_id=matched_cat.id if matched_cat else None,
            receipt_id=receipt.id,
            external_id=ai_result.codigo_identificacao,
            notes=f"[IA {ai_result.tipo_documento}] {ai_result.observacoes or ''}".strip(),
            source="ia_comprovante"
        )
        db.add(new_tx)
        target_tx = new_tx
        action_taken = f"Novo lançamento criado: {new_tx.description} (R$ {new_tx.amount:.2f}) na categoria {matched_cat.name if matched_cat else 'Geral'}."

    # Atualiza notas do comprovante
    receipt.notes = f"IA: {ai_result.estabelecimento} - R$ {ai_result.valor:.2f} ({ai_result.tipo_documento})"
    db.commit()

    return {
        "success": True,
        "action": action_taken,
        "details": ai_result.model_dump(),
        "transaction_id": target_tx.id if target_tx else None
    }


def process_all_unlinked_receipts(db: Session) -> Dict[str, Any]:
    unlinked = db.query(Receipt).filter(Receipt.transaction == None).all()
    results = []
    success_count = 0
    error_count = 0

    for r in unlinked:
        try:
            res = process_receipt_with_ai(r.id, db)
            results.append({
                "receipt_id": r.id,
                "filename": r.original_filename,
                "success": True,
                "action": res["action"]
            })
            success_count += 1
        except Exception as e:
            results.append({
                "receipt_id": r.id,
                "filename": r.original_filename,
                "success": False,
                "error": str(e)
            })
            error_count += 1

    return {
        "total_processed": len(unlinked),
        "success_count": success_count,
        "error_count": error_count,
        "items": results
    }
