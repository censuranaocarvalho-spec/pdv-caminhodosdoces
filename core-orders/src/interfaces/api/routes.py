from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List
from src.application.use_cases.create_order import CreateOrderUseCase

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])

class CustomerModel(BaseModel):
    phone: str
    name: str
    address: str

class ItemModel(BaseModel):
    productId: str
    productName: str
    quantity: int = Field(..., gt=0)
    unitPrice: float = Field(..., gt=0)

class CreateOrderRequest(BaseModel):
    channel: str = Field(..., description="WHATSAPP, TELEGRAM, IFOOD")
    customer: CustomerModel
    items: List[ItemModel]
    paymentType: str = Field("PARCIAL_50_50", description="PARCIAL_50_50 ou INTEGRAL")

@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(payload: CreateOrderRequest):
    try:
        use_case = CreateOrderUseCase()
        result = use_case.execute(payload.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
