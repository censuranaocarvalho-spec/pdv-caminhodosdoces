from dataclasses import dataclass, field
import uuid
from datetime import datetime

@dataclass
class FinancialTransaction:
    order_id: str
    amount: float
    transaction_type: str  # "DOWN_PAYMENT" ou "FINAL_PAYMENT"
    payment_method: str    # "PIX", "DINHEIRO", "CARTAO"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "CONFIRMED"

    def validate_amount(self):
        if self.amount <= 0:
            raise ValueError("O valor da transação financeira deve ser maior que zero.")
        return True
