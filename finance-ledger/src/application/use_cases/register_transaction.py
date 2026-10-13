from src.domain.entities import FinancialTransaction
import psycopg2
import pika
import json

DB_CONFIG = {
    "dbname": "pdv_caminhodosdoces",
    "user": "pdv_admin",
    "password": "pdv_secure_password_2026",
    "host": "localhost",
    "port": "5432"
}

def init_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS financial_ledger (
                id VARCHAR(36) PRIMARY KEY,
                order_id VARCHAR(36),
                amount NUMERIC(10, 2),
                transaction_type VARCHAR(50),
                payment_method VARCHAR(50),
                status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[AVISO DB FINANCE] Erro ao inicializar tabela: {e}")

def publish_event(event_type: str, payload: dict):
    try:
        credentials = pika.PlainCredentials('pdv_rabbit', 'pdv_rabbit_password')
        params = pika.ConnectionParameters('localhost', 5672, '/', credentials)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue='pdv_events', durable=True)
        
        event_message = {
            "eventType": event_type,
            "sourceModule": "finance-ledger",
            "payload": payload
        }
        
        channel.basic_publish(
            exchange='',
            routing_key='pdv_events',
            body=json.dumps(event_message)
        )
        connection.close()
    except Exception as e:
        print(f"[AVISO] Falha ao publicar evento financeiro no RabbitMQ: {e}")

class RegisterTransactionUseCase:
    def execute(self, data: dict) -> dict:
        init_db()

        transaction = FinancialTransaction(
            order_id=data["orderId"],
            amount=data["amount"],
            transaction_type=data.get("transactionType", "DOWN_PAYMENT"),
            payment_method=data.get("paymentMethod", "PIX")
        )
        transaction.validate_amount()

        # Persistência no banco de dados
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO financial_ledger (id, order_id, amount, transaction_type, payment_method, status)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (transaction.id, transaction.order_id, transaction.amount, transaction.transaction_type, transaction.payment_method, transaction.status)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

        # Publica evento de transação registrada
        publish_event("CASH_TRANSACTION_REGISTERED", {
            "transactionId": transaction.id,
            "orderId": transaction.order_id,
            "amount": transaction.amount,
            "type": transaction.transaction_type
        })

        return {
            "transactionId": transaction.id,
            "status": transaction.status,
            "amount": transaction.amount,
            "message": "Transação financeira registrada com sucesso!"
        }
