from src.domain.entities import ComplianceAudit
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
            CREATE TABLE IF NOT EXISTS compliance_audits (
                id VARCHAR(36) PRIMARY KEY,
                document_type VARCHAR(50),
                reference_id VARCHAR(36),
                status VARCHAR(50),
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[AVISO DB COMPLIANCE] Erro ao inicializar tabela: {e}")

def publish_event(event_type: str, payload: dict):
    try:
        credentials = pika.PlainCredentials('pdv_rabbit', 'pdv_rabbit_password')
        params = pika.ConnectionParameters('localhost', 5672, '/', credentials)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue='pdv_events', durable=True)
        
        event_message = {
            "eventType": event_type,
            "sourceModule": "compliance-governance",
            "payload": payload
        }
        
        channel.basic_publish(
            exchange='',
            routing_key='pdv_events',
            body=json.dumps(event_message)
        )
        connection.close()
    except Exception as e:
        print(f"[AVISO] Falha ao publicar evento Compliance no RabbitMQ: {e}")

class ValidateComplianceUseCase:
    def execute(self, data: dict) -> dict:
        init_db()

        audit = ComplianceAudit(
            document_type=data["documentType"],
            reference_id=data["referenceId"],
            details=data.get("details", "Verificação padrão realizada com sucesso.")
        )
        audit.validate_rules()

        # Persistência no banco de dados
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO compliance_audits (id, document_type, reference_id, status, details)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (audit.id, audit.document_type, audit.reference_id, audit.status, audit.details)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

        # Publica evento de auditoria concluída
        publish_event("COMPLIANCE_VERIFIED", {
            "auditId": audit.id,
            "documentType": audit.document_type,
            "referenceId": audit.reference_id,
            "status": audit.status
        })

        return {
            "auditId": audit.id,
            "documentType": audit.document_type,
            "status": audit.status,
            "message": "Auditoria de compliance registrada com sucesso!"
        }
