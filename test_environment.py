import psycopg2
import redis
import pika
import uuid
import sys

print("==================================================")
print("  INICIANDO TESTE DO AMBIENTE: Caminho dos Doces  ")
print("==================================================\n")

# 1. Teste do PostgreSQL e tabelas da Migration
try:
    conn = psycopg2.connect(
        dbname="pdv_caminhodosdoces",
        user="pdv_admin",
        password="pdv_secure_password_2026",
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor()
    print("[1/3] PostgreSQL: Conexão bem-sucedida! 🐘")
    
    # Inserção de Cliente e Pedido Teste com Regra 50/50
    customer_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())
    
    cursor.execute(
        "INSERT INTO customers (id, phone, name, address) VALUES (%s, %s, %s, %s);",
        (customer_id, "5511999998888", "Cliente Teste", "Rua dos Doces, 123")
    )
    
    cursor.execute(
        """
        INSERT INTO orders (id, channel, customer_id, status, payment_type, total_amount, paid_amount, pending_amount)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """,
        (order_id, "WHATSAPP", customer_id, "AGUARDANDO_SINAL", "PARCIAL_50_50", 100.00, 50.00, 50.00)
    )
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM orders;")
    total_orders = cursor.fetchone()[0]
    print(f"      -> Inserção e leitura de Pedido 50/50 OK! Total de pedidos no banco: {total_orders}")
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"[1/3] ERRO no PostgreSQL: {e}")
    sys.exit(1)

# 2. Teste do Redis
try:
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.set('teste_pdv', 'Ambiente OK')
    val = r.get('teste_pdv').decode('utf-8')
    print(f"[2/3] Redis: Conexão e leitura/escrita bem-sucedidas! ⚡ (Valor lido: '{val}')")
except Exception as e:
    print(f"[2/3] ERRO no Redis: {e}")
    sys.exit(1)

# 3. Teste do RabbitMQ
try:
    credentials = pika.PlainCredentials('pdv_rabbit', 'pdv_rabbit_password')
    parameters = pika.ConnectionParameters('localhost', 5672, '/', credentials)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue='teste_queue')
    channel.basic_publish(exchange='', routing_key='teste_queue', body='Evento Teste PDV')
    print("[3/3] RabbitMQ: Conexão e envio de mensagem de evento bem-sucedidos! 🐇")
    connection.close()
except Exception as e:
    print(f"[3/3] ERRO no RabbitMQ: {e}")
    sys.exit(1)

print("\n==================================================")
print("  RESULTADO: TODOS OS SERVIÇOS ESTÃO 100% OPERACIONAIS! 🚀  ")
print("==================================================")
