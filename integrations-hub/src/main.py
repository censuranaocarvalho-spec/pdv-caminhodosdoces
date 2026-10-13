from fastapi import FastAPI, APIRouter, HTTPException, status
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Integrations Hub - Caminho dos Doces", version="1.0.0")

router = APIRouter(prefix="/api/v1/integrations", tags=["Integrations Hub"])

class WhatsAppNotificationRequest(BaseModel):
    phone: str
    customerName: str
    orderId: str
    totalAmount: float
    message: str

@router.post("/whatsapp/send", status_code=status.HTTP_200_OK)
def send_whatsapp_notification(payload: WhatsAppNotificationRequest):
    print(f"\n[WHATSAPP GATEWAY] 📱 Enviando mensagem para {payload.phone} ({payload.customerName}):")
    print(f"--------------------------------------------------")
    print(f"{payload.message}")
    print(f"--------------------------------------------------\n")
    
    return {
        "status": "success",
        "recipient": payload.phone,
        "orderId": payload.orderId,
        "deliveryStatus": "SENT",
        "message": "Mensagem de WhatsApp disparada com sucesso pelo Integrations Hub!"
    }

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
