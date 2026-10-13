from fastapi import FastAPI
from src.interfaces.api.routes import router as finance_router

app = FastAPI(
    title="Caminho dos Doces - Finance Ledger API (Clean Architecture + DDD)",
    description="Microsserviço de Caixa e Gestão Financeira",
    version="2.0.0"
)

app.include_router(finance_router)

@app.get("/health")
def health_check():
    return {"status": "online", "module": "finance-ledger", "architecture": "Clean Architecture / DDD"}
