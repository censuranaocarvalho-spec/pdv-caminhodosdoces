# Finance Ledger Module (`finance-ledger`)

## Responsabilidade
Este módulo é responsável por gerenciar a consolidação financeira em tempo real da loja Caminho dos Doces. Ele calcula as métricas dos Cards do Dashboard, realiza a conciliação bancária de repasses e controla as diárias e taxas de entregadores.

---

## Módulos de Domínio

1. **Ledger & DRE (`src/ledger/`):**
   - **Valor Bruto:** Total transacionado em vendas sem deduções.
   - **Valor Líquido:** Receita efetiva após retenção de taxas (iFood, 99Food, MDR de cartões).
   - **Descontos/Taxas:** Discriminação de cupons, comissões de marketplaces e custos de operação.
   - **Controle 50/50:** Rastreabilidade de entradas de sinal e liquidação de saldo na entrega.

2. **Conciliação Bancária (`src/reconciliation/`):**
   - Integração Open Finance / API Bancária para batimento de extratos bancários.
   - Validação de baixas de PIX com identificador ponta a ponta (`EndToEndId`).

3. **Logística & Frete (`src/logistics/`):**
   - Apuração de acerto de contas diário por motoboy/entregador parceiro.
   - Cálculo de taxa de entrega acumulada vs. recebimento em dinheiro em campo.
