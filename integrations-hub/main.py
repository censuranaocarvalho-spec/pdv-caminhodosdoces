from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from abc import ABC, abstractmethod
import uuid
from datetime import datetime

app = FastAPI(
    title="Integrations Hub - Caminho dos Doces",
    description="Módulo 2: Webhooks e Fila de Mensagens WhatsApp",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

QUEUE_DB = []

class NotificationAdapter(ABC):
    @abstractmethod
    def send(self, recipient: str, message: str) -> dict:
        pass

class WhatsAppAdapter(NotificationAdapter):
    def send(self, recipient: str, message: str) -> dict:
        return {
            "adapter": "WhatsAppOfficialAPI",
            "recipient": recipient,
            "content": message,
            "status": "DISPARADO_COM_SUCESSO"
        }

def worker_process_notification(payload: dict):
    task_id = f"TSK-{uuid.uuid4().hex[:6].upper()}"
    adapter = WhatsAppAdapter()
    result = adapter.send(payload.get("recipient"), payload.get("message"))
    
    log_entry = {
        "taskId": task_id,
        "type": "WHATSAPP_CUPOM",
        "details": result,
        "processedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    QUEUE_DB.append(log_entry)

class NotificationRequest(BaseModel):
    channel: str
    recipient: str
    message: str

@app.post("/api/v1/integrations/notify", status_code=202)
def dispatch_notification(payload: NotificationRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(worker_process_notification, payload.dict())
    return {"message": "Notificação enfileirada no Hub com sucesso.", "status": "ACCEPTED"}

@app.get("/api/v1/integrations/queue/logs")
def list_queue_logs():
    return QUEUE_DB

@app.get("/health")
def health_check():
    return {"status": "healthy"}
