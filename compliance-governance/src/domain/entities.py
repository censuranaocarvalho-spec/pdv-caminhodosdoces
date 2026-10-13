from dataclasses import dataclass, field
import uuid

@dataclass
class ComplianceAudit:
    document_type: str  # "FISCAL_NOTA", "ANVISA_SANitaria", "LGPD_CONSENT"
    reference_id: str
    status: str = "COMPLIANT"
    details: str = "Aprovado em conformidade com as normas vigentes."
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def validate_rules(self):
        """Valida regras de negócio corporativas para a doceria."""
        if not self.reference_id:
            raise ValueError("ID de referência obrigatório para auditoria de compliance.")
        if self.document_type not in ["FISCAL_NOTA", "ANVISA_SANITARIA", "LGPD_CONSENT"]:
            raise ValueError("Tipo de documento de compliance inválido.")
        return True
