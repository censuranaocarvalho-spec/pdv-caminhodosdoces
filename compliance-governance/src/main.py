from fastapi import FastAPI
from src.interfaces.api.routes import router as compliance_router

app = FastAPI(
    title="Caminho dos Doces - Compliance Governance API (Clean Architecture + DDD)",
    description="Microsserviço de Governança Fiscal, Sanitária e LGPD",
    version="2.0.0"
)

app.include_router(compliance_router)

@app.get("/health")
def health_check():
    return {"status": "online", "module": "compliance-governance", "architecture": "Clean Architecture / DDD"}
