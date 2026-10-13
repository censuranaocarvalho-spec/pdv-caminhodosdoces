# Compliance & Governance Module (`compliance-governance`)

## Responsabilidade
Este módulo garante o cumprimento automatizado de leis, normas sanitárias e fiscalização contábil no PDV, aplicando o conceito de *Compliance by Design*. Oferece também o painel auditável com filtros parametrizados.

---

## Sub-módulos de Proteção

1. **Gestão de Privacidade & LGPD (`src/lgpd/`):**
   - Controle rígido de *Opt-In* e *Opt-Out* (mensagens de marketing e atualizações de pedidos via WhatsApp).
   - Rotina de anonimização e exclusão de dados a pedido do cliente (Direito ao Esquecimento).

2. **Vigilância Sanitária & Boas Práticas (`src/sanitary/`):**
   - Checklist diário/semanal da ANVISA (RDC 216/2004) para abertura e fechamento de cozinha/loja.
   - Monitoramento de validade de insumos e rotulagem automática de alergênicos (Glúten, Lactose, Amendoim) no cardápio digital.

3. **Conformidade Fiscal & Tributária (`src/fiscal/`):**
   - Discriminação automática de tributos aproximados (Lei 12.741/2012 - IBPT) nos cupons enviados por WhatsApp, Instagram e Facebook.
   - Retenção segura de logs de transações e comprovantes fiscais/não fiscais por 5 anos.

4. **Motor de Filtros & Auditoria (`src/audit/`):**
   - Painel central com filtros parametrizados por Período, Canal de Venda, Status de Conformidade e Tipo de Ator.
   - Exportação em 1-clique de relatórios para fiscalização sanitária e contábil.
