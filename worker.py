import pika
import json
import requests
import time

RABBIT_CONFIG = {
    "host": "localhost",
    "port": 5672,
    "credentials": pika.PlainCredentials('pdv_rabbit', 'pdv_rabbit_password')
}

def callback(ch, method, properties, body):
    try:
        body_str = body.decode('utf-8')
        event = json.loads(body_str)
        
        # Blindagem: Se não for um dicionário ou faltar o eventType, descarta a mensagem antiga/inválida
        if not isinstance(event, dict) or not event.get("eventType"):
            print(f"[AVISO] Mensagem antiga ou fora do padrão ignorada: {body_str}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        event_type = event.get("eventType")
        source = event.get("sourceModule")
        payload = event.get("payload", {})
        
        print(f"\n[EVENTO INTERCEPTADO] Tipo: {event_type} | Origem: {source}")
        print(f"Payload: {json.dumps(payload, indent=2)}")

        if event_type == "EXTERNAL_ORDER_WEBHOOK_RECEIVED":
            print(" -> [EDA Workflow] Webhook normalizado! Convertendo em pedido no core-orders...")
            order_payload = {
                "channel": payload.get("channel", "WHATSAPP"),
                "customer": payload.get("customer", {"phone": "5511988887777", "name": "Cliente Webhook", "address": "Balcão"}),
                "items": payload.get("items", [{"productId": "DOCE-GEN", "productName": "Doce Especial", "quantity": 1, "unitPrice": 100.00}]),
                "paymentType": "PARCIAL_50_50"
            }
            try:
                res = requests.post("http://localhost:8001/api/v1/orders", json=order_payload)
                print(f"    [core-orders Response]: {res.status_code} - {res.json()}")
            except Exception as e:
                print(f"    [Erro ao acionar core-orders]: {e}")

        elif event_type == "ORDER_CREATED":
            print(" -> [EDA Workflow] Pedido criado! Disparando ações no Financeiro e no CRM...")
            
            order_id = payload.get("orderId")
            down_payment = payload.get("downPayment", 0.0)
            finance_payload = {
                "orderId": order_id,
                "amount": down_payment,
                "transactionType": "DOWN_PAYMENT",
                "paymentMethod": "PIX"
            }
            try:
                res_fin = requests.post("http://localhost:8003/api/v1/finance/transactions", json=finance_payload)
                print(f"    [finance-ledger Response]: {res_fin.status_code} - {res_fin.json()}")
            except Exception as e:
                print(f"    [Erro ao acionar finance-ledger]: {e}")

            customer_phone = payload.get("customerPhone", "5511999999999")
            crm_payload = {
                "phone": customer_phone,
                "name": f"Cliente Pedido {order_id[:6]}",
                "address": "Endereço via Canal Digital"
            }
            try:
                res_crm = requests.post("http://localhost:8004/api/v1/crm/customers", json=crm_payload)
                print(f"    [crm-marketing Response]: {res_crm.status_code} - {res_crm.json()}")
            except Exception as e:
                print(f"    [Erro ao acionar crm-marketing]: {e}")

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"[ERRO NO WORKER] Falha ao processar evento: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False) # Descarta mensagem corrompida

def main():
    print("[PDV WORKER] Iniciando consumidor assíncrono de eventos RabbitMQ...")
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(**RABBIT_CONFIG))
            channel = connection.channel()
            channel.queue_declare(queue='pdv_events')
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue='pdv_events', on_message_callback=callback)
            
            print("[PDV WORKER] Escutando barramento 'pdv_events' em tempo real...")
            channel.start_consuming()
        except Exception as e:
            print(f"[CONEXÃO PERDIDA] Tentando reconectar ao RabbitMQ em 5s... Erro: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
