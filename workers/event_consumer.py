import pika
import json
import sys
import os

RABBIT_CONFIG = {
    "host": "localhost",
    "port": 5672,
    "user": "pdv_rabbit",
    "password": "pdv_rabbit_password",
    "queue": "pdv_events"
}

def callback(ch, method, properties, body):
    try:
        event = json.loads(body.decode())
        event_type = event.get("eventType")
        source = event.get("sourceModule")
        payload = event.get("payload")
        
        print(f"\n[EVENTO CAPTURADO] 📥 Origem: {source} | Tipo: {event_type}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Exemplo de Automação Reativa (DDD / Business Rules)
        if event_type == "EXTERNAL_ORDER_WEBHOOK_RECEIVED":
            print(f"-> [AUTOMAÇÃO CRM] Novo pedido externo detectado do canal {payload.get('channel')}. Acionando boas-vindas...")
        elif event_type == "CASH_TRANSACTION_REGISTERED":
            print(f"-> [AUTOMAÇÃO FINANCEIRA] Transação registrada. Saldo atualizado no caixa.")
        
        # Confirma o processamento da mensagem para o RabbitMQ (ACK)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except Exception as e:
        print(f"[ERRO NO WORKER] Falha ao processar evento: {e}")
        # Rejeita e reenfiletera ou descarta conforme política
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def start_consumer():
    print("🔄 Iniciando Background Worker do RabbitMQ para a Caminho dos Doces...")
    try:
        credentials = pika.PlainCredentials(RABBIT_CONFIG["user"], RABBIT_CONFIG["password"])
        params = pika.ConnectionParameters(
            host=RABBIT_CONFIG["host"],
            port=RABBIT_CONFIG["port"],
            credentials=credentials
        )
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        
        channel.queue_declare(queue=RABBIT_CONFIG["queue"], durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=RABBIT_CONFIG["queue"], on_message_callback=callback)
        
        print(f"[*] Aguardando eventos na fila '{RABBIT_CONFIG['queue']}'. Pressione CTRL+C para sair.")
        channel.start_consuming()
        
    except KeyboardInterrupt:
        print("\n[!] Worker interrompido pelo usuário.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
    except Exception as e:
        print(f"[ERRO DE CONEXÃO RABBITMQ] {e}")

if __name__ == "__main__":
    start_consumer()
