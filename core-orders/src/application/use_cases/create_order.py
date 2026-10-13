from src.domain.entities import Order, OrderItem
import psycopg2
import pika
import json
import os

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "pdv_caminhodosdoces"),
    "user": os.getenv("DB_USER", "pdv_admin"),
    "password": os.getenv("DB_PASSWORD", "pdv_secure_password_2026"),
    "host": os.getenv("DB_HOST", "postgres"),
    "port": os.getenv("DB_PORT", "5432")
}

def init_db():
    """Garante que a tabela 'orders' existe no banco de dados."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id VARCHAR(36) PRIMARY KEY,
                channel VARCHAR(50),
                customer_phone VARCHAR(50),
                customer_name VARCHAR(100),
                total_amount NUMERIC(10, 2),
                status VARCHAR(50),
                payment_type VARCHAR(50),
                down_payment NUMERIC(10, 2),
                remaining_balance NUMERIC(10, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[AVISO DB] Erro ao inicializar tabela: {e}")

def publish_event(event_type: str, payload: dict):
    try:
        rabbit_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        rabbit_port = int(os.getenv("RABBITMQ_PORT", 5672))
        rabbit_user = os.getenv("RABBITMQ_USER", "pdv_rabbit")
        rabbit_pass = os.getenv("RABBITMQ_PASSWORD", "pdv_rabbit_password")

        credentials = pika.PlainCredentials(rabbit_user, rabbit_pass)
        params = pika.ConnectionParameters(rabbit_host, rabbit_port, '/', credentials)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue='pdv_events', durable=True)
        
        event_message = {
            "eventType": event_type,
            "sourceModule": "core-orders",
            "payload": payload
        }
        
        channel.basic_publish(
            exchange='',
            routing_key='pdv_events',
            body=json.dumps(event_message)
        )
        connection.close()
    except Exception as e:
        print(f"[AVISO] Falha ao publicar evento no RabbitMQ: {e}")

class CreateOrderUseCase:
    def execute(self, order_data: dict) -> dict:
        # Garante que a tabela existe antes de inserir
        init_db()

        # 1. Instancia os itens e a Entidade de Domínio
        items = [
            OrderItem(
                product_id=i["productId"],
                product_name=i["productName"],
                quantity=i["quantity"],
                unit_price=i["unitPrice"]
            ) for i in order_data["items"]
        ]
        
        order = Order(
            channel=order_data["channel"],
            customer_phone=order_data["customer"]["phone"],
            customer_name=order_data["customer"]["name"],
            customer_address=order_data["customer"]["address"],
            items=items,
            payment_type=order_data.get("paymentType", "PARCIAL_50_50")
        )
        
        total_amount = order.calculate_totals_and_split()

        # 2. Persistência no Banco de Dados
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO orders (id, channel, customer_phone, customer_name, total_amount, status, payment_type, down_payment, remaining_balance)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (order.id, order.channel, order.customer_phone, order.customer_name, total_amount, order.status, order.payment_type, order.down_payment, order.remaining_balance)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

        # 3. Disparo de Evento Assíncrono
        publish_event("ORDER_CREATED", {
            "orderId": order.id,
            "customerPhone": order.customer_phone,
            "totalAmount": total_amount,
            "downPayment": order.down_payment,
            "remainingBalance": order.remaining_balance,
            "paymentType": order.payment_type
        })

        return {
            "orderId": order.id,
            "status": order.status,
            "totalAmount": total_amount,
            "downPayment": order.down_payment,
            "remainingBalance": order.remaining_balance,
            "message": "Pedido criado com sucesso sob as regras DDD!"
        }