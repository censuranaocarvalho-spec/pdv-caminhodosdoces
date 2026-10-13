from src.domain.entities import Customer
from datetime import datetime, timezone
from uuid import uuid4

class RegisterCustomerUseCase:
    def __init__(self, customer_repository):
        self.customer_repository = customer_repository

    def execute(self, phone: str, name: str, address: str, customer_id: str = None) -> Customer:
        final_id = customer_id or str(uuid4())
        customer = Customer(
            id=final_id,
            phone=phone,
            name=name,
            address=address,
            loyalty_points=10,
            segment="NEW",
            created_at=datetime.now(timezone.utc)
        )
        return self.customer_repository.save(customer)
