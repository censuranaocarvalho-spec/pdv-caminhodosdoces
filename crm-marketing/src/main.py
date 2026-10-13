from fastapi import FastAPI
from src.interfaces.api.routes import router as crm_router

app = FastAPI(
    title="Caminho dos Doces - CRM Marketing API (Clean Architecture + DDD)",
    description="Microsserviço de Relacionamento e Fidelização de Clientes",
    version="2.0.0"
)

app.include_router(crm_router)

@app.get("/health")
def health_check():
    return {"status": "online", "module": "crm-marketing", "architecture": "Clean Architecture / DDD"}
