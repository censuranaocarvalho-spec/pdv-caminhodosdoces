from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from src.application.use_cases.register_transaction import RegisterTransactionUseCase

router = APIRouter(prefix="/api/v1/finance", tags=["Finance Ledger"])

class TransactionRequest(BaseModel):
    orderId: str
    amount: float = Field(..., gt=0)
    transactionType: str = Field("DOWN_PAYMENT", description="DOWN_PAYMENT ou FINAL_PAYMENT")
    paymentMethod: str = Field("PIX", description="PIX, DINHEIRO, CARTAO")

@router.post("/transactions", status_code=status.HTTP_201_CREATED)
def register_transaction(payload: TransactionRequest):
    try:
        use_case = RegisterTransactionUseCase()
        result = use_case.execute(payload.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
