import psycopg2
import redis
import pika
import uuid
import sys

print("==================================================")
print("  CAMINHO DOS DOCES: Migration & Teste de Ambiente")
print("==================================================\n")

# 1. Conectar ao PostgreSQL, criar as tabelas (Migration) e testar
try:
    conn = psycopg2.connect(
        dbname="pdv_caminhodosdoces",
        user="pdv_admin",
        password="pdv_secure_password_2026",
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor()
    print("[1/4] PostgreSQL: Conexão estabelecida com sucesso! 🐘")

    # Executando o Schema SQL diretamente via Python
    cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            phone VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            address TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cash_register_sessions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            operator_id VARCHAR(50) NOT NULL,
            opened_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP WITH TIME ZONE,
            initial_balance NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
            current_balance NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
            status VARCHAR(20) NOT NULL DEFAULT 'ABERTO'
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            channel VARCHAR(30) NOT NULL,
            customer_id UUID REFERENCES customers(id),
            status VARCHAR(30) NOT NULL,
            payment_type VARCHAR(20) NOT NULL,
            total_amount NUMERIC(10, 2) NOT NULL,
            paid_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
            pending_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    print("[2/4] Tabelas criadas/verificadas com sucesso no PostgreSQL! 📋")

    # Inserção de Ped teste (Regra 50/50)
    customer_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())
    
    cursor.execute(
        "INSERT INTO customers (id, phone, name, address) VALUES (%s, %s, %s, %s) ON CONFLICT (phone) DO NOTHING;",
        (customer_id, "5511999998888", "Cliente Teste", "Rua dos Doces, 123")
    )
    
    cursor.execute(
        """
        INSERT INTO orders (id, channel, customer_id, status, payment_type, total_amount, paid_amount, pending_amount)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """,
        (order_id, "WHATSAPP", customer_id, "AGUARDANDO_SINAL", "PARCIAL_50_50", 150.00, 75.00, 75.00)
    )
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM orders;")
    total_orders = cursor.fetchone()[0]
    print(f"      -> Inserção de Pedido 50/50 OK! Total de pedidos cadastrados: {total_orders}")
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"[ERRO] Falha no PostgreSQL: {e}")
    sys.exit(1)

# 2. Teste do Redis
try:
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.set('pdv_status', 'Online e Operacional')
    val = r.get('pdv_status').decode('utf-8')
    print(f"[3/4] Redis: Conexão e cache OK! ⚡ (Valor: '{val}')")
except Exception as e:
    print(f"[ERRO] Falha no Redis: {e}")
    sys.exit(1)

# 3. Teste do RabbitMQ
try:
    credentials = pika.PlainCredentials('pdv_rabbit', 'pdv_rabbit_password')
    parameters = pika.ConnectionParameters('localhost', 5672, '/', credentials)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue='pdv_events')
    channel.basic_publish(exchange='', routing_key='pdv_events', body='{"event": "SYSTEM_STARTED"}')
    print("[4/4] RabbitMQ: Conexão e mensageria de eventos OK! 🐇")
    connection.close()
except Exception as e:
    print(f"[ERRO] Falha no RabbitMQ: {e}")
    sys.exit(1)

print("\n==================================================")
print("  SUCESSO ABSOLUTO: AMBIENTE 100% PRONTO E TESTADO! 🚀")
print("==================================================")
