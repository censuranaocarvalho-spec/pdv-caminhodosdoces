from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from src.application.use_cases.validate_compliance import ValidateComplianceUseCase

router = APIRouter(prefix="/api/v1/compliance", tags=["Compliance & Governance"])

class ComplianceRequest(BaseModel):
    documentType: str = Field(..., description="FISCAL_NOTA, ANVISA_SANITARIA ou LGPD_CONSENT")
    referenceId: str
    details: str = Field("Conformidade verificada.")

@router.post("/validate", status_code=status.HTTP_201_CREATED)
def validate_compliance(payload: ComplianceRequest):
    try:
        use_case = ValidateComplianceUseCase()
        result = use_case.execute(payload.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
