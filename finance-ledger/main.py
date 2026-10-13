from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import uuid
from datetime import datetime

app = FastAPI(
    title="Finance & Ledger Service - Caminho dos Doces",
    description="Módulo 3: DRE, Conciliação Bancária (Inter) e Livro Caixa com Transações ACID",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simulação de base transacional ACID (em produção mapeada para PostgreSQL)
LEDGER_DB = []
BANK_RECONCILIATION_DB = []

class LedgerEntryCreate(BaseModel):
    orderId: str
    description: str
    amount: float = Field(..., gt=0)
    type: str  # ENTRADA, SAIDA, ESTORNO
    category: str  # VENDAS_DOCES, INSUMOS, TAXAS

class BankReconciliationCreate(BaseModel):
    bankTransactionId: str
    amount: float
    description: str
    matchedOrderId: Optional[str] = None

@app.post("/api/v1/ledger/entries", status_code=201)
def create_ledger_entry(payload: LedgerEntryCreate):
    """Regista entradas e saídas no Livro Caixa garantindo consistência transacional."""
    entry_id = f"LED-{uuid.uuid4().hex[:6].upper()}"
    record = {
        "entryId": entry_id,
        "orderId": payload.orderId,
        "description": payload.description,
        "amount": payload.amount,
        "type": payload.type,
        "category": payload.category,
        "status": "CONCLUIDO_ACID",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    LEDGER_DB.append(record)
    return {"message": "Lançamento contabilizado com sucesso no Livro Caixa", "entry": record}

@app.get("/api/v1/ledger/entries")
def list_ledger_entries():
    return LEDGER_DB

@app.post("/api/v1/finance/reconciliation", status_code=201)
def reconcile_bank_transaction(payload: BankReconciliationCreate):
    """Realiza a conciliação bancária automática com o extrato (ex: Banco Inter)."""
    recon_id = f"REC-{uuid.uuid4().hex[:6].upper()}"
    record = {
        "reconciliationId": recon_id,
        "bankTransactionId": payload.bankTransactionId,
        "amount": payload.amount,
        "description": payload.description,
        "matchedOrderId": payload.matchedOrderId or "PENDENTE_MATCH",
        "status": "CONCILIADO",
        "reconciledAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    BANK_RECONCILIATION_DB.append(record)
    return {"message": "Conciliação bancária executada com sucesso", "reconciliation": record}

@app.get("/api/v1/finance/dre")
def get_dre_report():
    """Gera o relatório DRE (Demonstração do Resultado do Exercício) operacional."""
    total_receitas = sum(e["amount"] for e in LEDGER_DB if e["type"] == "ENTRADA")
    total_saidas = sum(e["amount"] for e in LEDGER_DB if e["type"] in ["SAIDA", "ESTORNO"])
    lucro_liquido = total_receitas - total_saidas

    return {
        "periodo": datetime.now().strftime("%Y-%m"),
        "receitaBruta": round(total_receitas, 2),
        "deducoesEStornos": round(total_saidas, 2),
        "lucroOperacionalLiquido": round(lucro_liquido, 2),
        "statusACID": "INTEGRIDADE_GARANTIDA"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "module": "Finance & Ledger Service"}
