from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
from datetime import datetime

app = FastAPI(title="CRM & Marketing Microservice", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CUSTOMERS_DB = []

class CustomerCreate(BaseModel):
    name: str
    phone: str
    address: str
    channel: str

@app.post("/api/v1/customers", status_code=201)
def register_customer(customer: CustomerCreate):
    for c in CUSTOMERS_DB:
        if c["phone"] == customer.phone:
            c["ordersCount"] = c.get("ordersCount", 1) + 1
            c["lastInteraction"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return {"message": "Cliente atualizado", "customerId": c["customerId"], "customer": c}
    
    customer_id = f"CLI-{uuid.uuid4().hex[:6].upper()}"
    new_customer = {
        "customerId": customer_id,
        "name": customer.name,
        "phone": customer.phone,
        "address": customer.address,
        "favoriteChannel": customer.channel,
        "ordersCount": 1,
        "registeredAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    CUSTOMERS_DB.append(new_customer)
    return {"message": "Cliente registado no CRM", "customerId": customer_id, "customer": new_customer}

@app.get("/api/v1/customers")
def list_customers():
    return CUSTOMERS_DB

@app.get("/health")
def health_check():
    return {"status": "healthy"}
