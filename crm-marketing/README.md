# CRM & Marketing Module (`crm-marketing`)

## Responsabilidade
Este módulo gerencia o relacionamento com o cliente final, a captação e retenção de contatos (LTV), a régua de pós-venda com avaliação de satisfação interna e a automação de postagens em redes sociais.

---

## Módulos de Domínio

1. **Feedback & Pós-Venda (`src/feedback/`):**
   - Disparo automatizado de pesquisa de satisfação pós-entrega (1 a 5 estrelas) via WhatsApp.
   - **Filtro de Retenção:**
     - **Notas 4-5 (Promotores):** Envio de mensagem de agradecimento, cupom de fidelidade e link para avaliação pública.
     - **Notas 1-3 (Detratores):** Alerta em tempo real no painel do gerente para intervenção humana antes de avaliações externas negativas.

2. **Retenção & LTV (`src/retention/`):**
   - Perfil de compra do cliente (histórico unificado entre iFood, WhatsApp, Instagram, Facebook e Balcão).
   - Identificação de clientes inativos (ex: sem compras há 20 dias) e disparo de ofertas personalizadas.

3. **Social Publisher (`src/social/`):**
   - Agendamento e publicação automatizada de promoções/produtos em destaque nas redes sociais (Meta Graph API / Instagram / Facebook).
