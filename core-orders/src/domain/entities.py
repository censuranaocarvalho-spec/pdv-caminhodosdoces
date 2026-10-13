from dataclasses import dataclass, field
from typing import List
import uuid

@dataclass
class OrderItem:
    product_id: str
    product_name: str
    quantity: int
    unit_price: float

    @property
    def total_price(self) -> float:
        return self.quantity * self.unit_price

@dataclass
class Order:
    customer_phone: str
    customer_name: str
    customer_address: str
    items: List[OrderItem]
    channel: str = "WHATSAPP"
    payment_type: str = "PARCIAL_50_50"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "AGUARDANDO_SINAL"
    down_payment: float = 0.0
    remaining_balance: float = 0.0

    def calculate_totals_and_split(self):
        """Aplica a regra de negócio central: Divisão 50/50 do valor total."""
        total_amount = sum(item.total_price for item in self.items)
        if self.payment_type == "PARCIAL_50_50":
            self.down_payment = round(total_amount / 2, 2)
            self.remaining_balance = round(total_amount - self.down_payment, 2)
        else:
            self.down_payment = round(total_amount, 2)
            self.remaining_balance = 0.0
        return total_amount
