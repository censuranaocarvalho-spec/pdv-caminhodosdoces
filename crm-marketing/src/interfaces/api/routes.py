from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone
import psycopg2

router = APIRouter(prefix="/api/v1/crm", tags=["CRM Marketing"])

class CustomerCreateRequest(BaseModel):
    id: Optional[str] = None
    phone: str
    name: str
    address: str

def get_db_connection():
    return psycopg2.connect(
        dbname="pdv_caminhodosdoces",
        user="pdv_admin",
        password="pdv_secure_password_2026",
        host="localhost",
        port="5432"
    )

def init_crm_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS crm_customers (
                id VARCHAR(36) PRIMARY KEY,
                phone VARCHAR(20) NOT NULL,
                name VARCHAR(100) NOT NULL,
                address TEXT NOT NULL,
                loyalty_points INT DEFAULT 0,
                segment VARCHAR(50) DEFAULT 'NEW',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[AVISO] Erro ao inicializar tabela crm_customers: {e}")

init_crm_db()

@router.post("/customers", status_code=status.HTTP_201_CREATED)
def register_customer(body: CustomerCreateRequest):
    try:
        customer_id = body.id or str(uuid4())
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            """
            INSERT INTO crm_customers (id, phone, name, address, loyalty_points, segment, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
            """,
            (customer_id, body.phone, body.name, body.address, 10, "NEW", datetime.now(timezone.utc))
        )
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "status": "success",
            "customerId": customer_id,
            "message": "Cliente cadastrado e pontuado no CRM com sucesso!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
