# core-orders/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime

app = FastAPI(
    title="Core Order Service - Caminho dos Doces",
    description="Módulo 1: Gestão de Pedidos, Caixa, Métodos de Pagamento e 50/50",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Armazenamento transacional em memória (preparado para persistência ACID)
ORDERS_DB = []
CASHIER_SESSION = {"status": "ABERTO", "balance": 0.0, "openedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

class CustomerInfo(BaseModel):
    name: str
    phone: str
    address: str
    channel: str  # WHATSAPP, IFOOD, BALCAO, INSTAGRAM

class OrderItem(BaseModel):
    productId: str
    productName: str
    quantity: int = Field(..., gt=0)
    unitPrice: float = Field(..., gt=0)

class PaymentPayload(BaseModel):
    method: str  # DINHEIRO, PIX, CREDITO, DEBITO_DINHEIRO, CREDITO_DINHEIRO
    installments: Optional[int] = 1  # Máximo 5x no crédito
    cash_amount: Optional[float] = 0.0  # Usado em pagamentos mistos

class OrderCreateRequest(BaseModel):
    customer: CustomerInfo
    items: List[OrderItem]
    payment: PaymentPayload

@app.post("/api/v1/orders", status_code=201)
def create_order(payload: OrderCreateRequest):
    if CASHIER_SESSION["status"] != "ABERTO":
        raise HTTPException(status_code=400, detail="O caixa está fechado. Abra o caixa antes de registar pedidos.")

    order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
    
    # 1. Cálculo de Subtotal e Juros de Cartão de Crédito (até 5x, juros por conta do cliente)
    subtotal = sum(item.quantity * item.unitPrice for item in payload.items)
    final_amount = subtotal
    payment_desc = payload.payment.method

    if payload.payment.method == "CREDITO":
        if not payload.payment.installments or payload.payment.installments > 5:
            raise HTTPException(status_code=400, detail="O parcelamento máximo permitido no crédito é de 5 vezes.")
        if payload.payment.installments > 1:
            taxa_juros_mensal = 0.0199  # 1.99% a.m. repassado ao cliente
            final_amount = subtotal * (1 + (taxa_juros_mensal * payload.payment.installments))
            payment_desc = f"CARTÃO CRÉDITO ({payload.payment.installments}x com juros)"

    elif payload.payment.method in ["DEBITO_DINHEIRO", "CREDITO_DINHEIRO"]:
        if payload.payment.cash_amount <= 0 or payload.payment.cash_amount >= final_amount:
            raise HTTPException(status_code=400, detail="Valor em dinheiro inválido para o pagamento misto.")
        payment_desc = f"MISTO ({payload.payment.method.split('_')[0]} + Dinheiro: R$ {payload.payment.cash_amount:.2f})"

    # 2. Regra de Negócio 50/50 (Específica para PIX: 50% entrada + 50% na entrega)
    payment_status = "PAGO_INTEGRAL"
    sinal_amount = final_amount
    if payload.payment.method == "PIX":
        sinal_amount = round(final_amount * 0.5, 2)
        payment_status = "AGUARDANDO_SEGUNDA_PARTE_ENTREGA"

    order_record = {
        "orderId": order_id,
        "channel": payload.customer.channel,
        "customerName": payload.customer.name,
        "phone": payload.customer.phone,
        "address": payload.customer.address,
        "subtotal": round(subtotal, 2),
        "totalAmount": round(final_amount, 2),
        "sinalAmount": round(sinal_amount, 2),
        "paymentMethod": payment_desc,
        "paymentStatus": payment_status,
        "status": "EM_PRODUCAO",
        "items": [i.dict() for i in payload.items],
        "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    ORDERS_DB.append(order_record)
    CASHIER_SESSION["balance"] += sinal_amount

    return {
        "message": "Pedido registado com sucesso na Frente de Caixa",
        "orderId": order_id,
        "order": order_record
    }

@app.get("/api/v1/orders")
def list_orders():
    return ORDERS_DB

@app.patch("/api/v1/orders/{order_id}/cancel")
def cancel_order(order_id: str):
    """Cancela o pedido mantendo a integridade operacional da cozinha."""
    for order in ORDERS_DB:
        if order["orderId"] == order_id:
            if order["status"] == "CONCLUIDO":
                raise HTTPException(status_code=400, detail="Impossível cancelar um pedido concluído. Utilize o fluxo de estorno financeiro.")
            order["status"] = "CANCELADO"
            return {"message": f"Pedido {order_id} cancelado com segurança.", "order": order}
    raise HTTPException(status_code=404, detail="Pedido não encontrado.")

@app.get("/api/v1/cashier/status")
def cashier_status():
    return CASHIER_SESSION

@app.get("/health")
def health_check():
    return {"status": "healthy", "module": "Core Order Service"}