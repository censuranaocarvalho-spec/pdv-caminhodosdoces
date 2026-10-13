# Integrations Hub Module (`integrations-hub`)

## Responsabilidade
Este módulo atua como a camada de adaptação (Adapter Pattern) e normalização de payloads para todos os canais de vendas externos e robôs de atendimento da loja Caminho dos Doces.

---

## Módulos de Integração

1. **iFood API & Webhooks (`src/ifood/`):**
   - Recepção de novos pedidos e confirmação de status (`PLACED`, `CONFIRMED`, `DISPATCHED`).
   - Normalização das taxas do aplicativo para repasse ao módulo financeiro.

2. **99Food API (`src/ninetynine/`):**
   - Polling/Webhook de ordens de entrega e atualização de catálogo/disponibilidade.

3. **WhatsApp, Instagram e Facebook (`src/whatsapp/`):**
   - Envio automático de comprovantes (Cupom Não Fiscal em PDF/Imagem).
   - Fluxo de avaliação interna pós-venda (1 a 5 estrelas) e disparo de links de satisfação.
   - Gestão de Opt-in/Opt-out para conformidade com a LGPD.
