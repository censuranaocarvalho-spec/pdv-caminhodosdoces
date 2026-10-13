from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
import requests
import os
import re

app = FastAPI(
    title="Core Order Service - Caminho dos Doces",
    version="2.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ORDERS_DB = []
CASHIER_SESSION = {"status": "ABERTO", "balance": 0.0, "openedAt": "2026-10-12 22:05:49"}

FINANCE_URL = os.getenv("FINANCE_URL", "http://finance-ledger:8003/api/v1/ledger/entries")
INTEGRATIONS_URL = os.getenv("INTEGRATIONS_URL", "http://integrations-hub:8002/api/v1/integrations/notify")

def validar_cpf(cpf: str) -> bool:
    if not cpf:
        return True  # Opcional
    cpf_nums = re.sub(r'\D', '', cpf)
    if len(cpf_nums) != 11:
        return False
    if cpf_nums == cpf_nums[0] * 11:
        return False
    
    # Validação do 1º dígito
    soma = sum(int(cpf_nums[i]) * (10 - i) for i in range(9))
    digito1 = (soma * 10) % 11
    if digito1 == 10:
        digito1 = 0
    if digito1 != int(cpf_nums[9]):
        return False
        
    # Validação do 2º dígito
    soma = sum(int(cpf_nums[i]) * (11 - i) for i in range(10))
    digito2 = (soma * 10) % 11
    if digito2 == 10:
        digito2 = 0
    if digito2 != int(cpf_nums[10]):
        return False
        
    return True

class CustomerInfo(BaseModel):
    name: str
    phone: str
    referral: str
    cpf: Optional[str] = ""

class LogisticsInfo(BaseModel):
    event_date: str
    event_time: str
    delivery_method: str
    address: Optional[str] = ""

class OrderItem(BaseModel):
    productId: str
    productName: str
    quantity: int = Field(..., gt=0)
    unitPrice: float = Field(..., gt=0)

class ChatRestrictionsInfo(BaseModel):
    theme_colors_topper: str
    alteration_deadline: str
    allergies: Optional[str] = "Nenhuma"
    extra_observations: Optional[str] = ""

class PaymentPayload(BaseModel):
    method: str
    installments: Optional[int] = 1
    delivery_fee: Optional[float] = 0.0

class OrderCreateRequest(BaseModel):
    customer: CustomerInfo
    logistics: LogisticsInfo
    items: List[OrderItem]
    chat_restrictions: ChatRestrictionsInfo
    payment: PaymentPayload

@app.post("/api/v1/orders", status_code=201)
def create_order(payload: OrderCreateRequest):
    if CASHIER_SESSION["status"] != "ABERTO":
        raise HTTPException(status_code=400, detail="O caixa está fechado.")

    if payload.customer.cpf and not validar_cpf(payload.customer.cpf):
        raise HTTPException(status_code=400, detail="CPF inválido ou composto por dígitos repetidos. Verifique o número informado.")

    order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
    
    subtotal = sum(i.quantity * i.unitPrice for i in payload.items)
    delivery_fee = payload.payment.delivery_fee
    total_amount = subtotal + delivery_fee
    
    final_amount = total_amount
    payment_desc = payload.payment.method

    if payload.payment.method == "CREDITO":
        if payload.payment.installments and payload.payment.installments > 1:
            if payload.payment.installments > 5:
                raise HTTPException(status_code=400, detail="Parcelamento máximo de 5 vezes.")
            taxa_juros = 0.0199 * payload.payment.installments
            final_amount = total_amount * (1 + taxa_juros)
            payment_desc = f"CARTÃO CRÉDITO ({payload.payment.installments}x com juros)"

    sinal_amount = round(final_amount * 0.5, 2) if payload.payment.method == "PIX" else round(final_amount, 2)
    restante_amount = round(final_amount - sinal_amount, 2)

    order_record = {
        "orderId": order_id,
        "customer": payload.customer.dict(),
        "logistics": payload.logistics.dict(),
        "items": [i.dict() for i in payload.items],
        "chat_restrictions": payload.chat_restrictions.dict(),
        "subtotal": round(subtotal, 2),
        "deliveryFee": round(delivery_fee, 2),
        "totalAmount": round(final_amount, 2),
        "sinalAmount": sinal_amount,
        "restanteAmount": restante_amount,
        "paymentMethod": payment_desc,
        "status": "PENDENTE",
        "createdAt": "2026-10-12 22:05:49"
    }
    
    ORDERS_DB.append(order_record)
    CASHIER_SESSION["balance"] += sinal_amount

    try:
        requests.post(FINANCE_URL, json={
            "orderId": order_id,
            "description": f"Recebimento ({payment_desc}) - Pedido {order_id}",
            "amount": sinal_amount,
            "type": "ENTRADA",
            "category": "VENDAS_DOCES"
        }, timeout=3)
    except Exception as e:
        print(f"Aviso Finance Ledger: {e}")

    return {"message": "Pedido criado com sucesso", "orderId": order_id, "order": order_record}

@app.post("/api/v1/orders/{order_id}/send-whatsapp")
def send_order_whatsapp(order_id: str):
    order = next((o for o in ORDERS_DB if o["orderId"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    
    cust = order["customer"]
    log = order["logistics"]
    chat = order["chat_restrictions"]
    items_lines = "\n".join([f"• {i['quantity']}x {i['productName']} — R$ {i['unitPrice']:.2f}" for i in order["items"]])
    
    obs_restante = ""
    if order['restanteAmount'] > 0:
        obs_restante = f"\n⚠️ *LEMBRETE:* Resta o valor de *R$ {order['restanteAmount']:.2f}* a ser quitado (em Dinheiro/Pix/Cartão) no momento da entrega/retirada!"

    cupom_msg = f"""🧾 *CUPOM NÃO FISCAL - COMPROVANTE* 🧾
----------------------------------------
🧁 *CAMINHO DOS DOCES* 🧁
Confeitaria Artesanal
----------------------------------------
*DADOS DO CLIENTE:*
- Nome: {cust['name']}
- CPF na Nota: {cust.get('cpf') or 'Não informado'}
- Telefone: {cust['phone']}
- Canal: {cust['referral']}

*LOGÍSTICA E ENTREGA:*
- Data/Hora: {log['event_date']} às {log['event_time']}
- Modalidade: {log['delivery_method']}
- Endereço: {log.get('address') or 'Retirada na Loja'}

*ITENS DO PEDIDO:*
{items_lines}

*DETALHES & RESTRIÇÕES:*
- Tema/Cores/Topper: {chat['theme_colors_topper']}
- Prazo Limite Alterações: {chat['alteration_deadline']}
- Alergias: {chat['allergies']}

----------------------------------------
*RESUMO FINANCEIRO:*
- Subtotal Produtos: R$ {order['subtotal']:.2f}
- Taxa de Entrega: R$ {order['deliveryFee']:.2f}
- *VALOR TOTAL:* R$ {order['totalAmount']:.2f}

- *Forma de Pagamento:* {order['paymentMethod']}
- *Valor Pago Agora (Sinal):* R$ {order['sinalAmount']:.2f}
- *Restante a Pagar:* R$ {order['restanteAmount']:.2f}
{obs_restante}
----------------------------------------
Obrigado pela preferência! ✨"""

    try:
        res = requests.post(INTEGRATIONS_URL, json={
            "channel": "WHATSAPP",
            "recipient": cust['phone'],
            "message": cupom_msg
        }, timeout=3)
        if res.status_code not in [200, 201, 202]:
            raise HTTPException(status_code=500, detail="Erro no Hub de Integrações.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha de conexão com Hub: {e}")

    return {"message": "Cupom não fiscal enviado com sucesso!", "recipient": cust['phone']}

@app.get("/api/v1/orders")
def list_orders():
    return ORDERS_DB

@app.get("/api/v1/cashier/status")
def cashier_status():
    return CASHIER_SESSION

@app.get("/health")
def health_check():
    return {"status": "healthy"}
