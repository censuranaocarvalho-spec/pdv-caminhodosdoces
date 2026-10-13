#!/bin/bash

PROJECT_DIR="/home/fagnersfreitas/Documentos/pdv-caminhodosdoces"
cd "$PROJECT_DIR" || exit 1

mkdir -p logs

echo "🚀 Iniciando ecossistema Caminho dos Doces (Microsserviços)..."

# 1. Core Orders (Port 8001)
echo "Iniciando Core Orders na porta 8001..."
python3 -m uvicorn core-orders.src.main:app --host 0.0.0.0 --port 8001 > logs/core-orders.log 2>&1 &
echo $! > logs/core-orders.pid

# 2. Integrations Hub (Port 8002)
echo "Iniciando Integrations Hub na porta 8002..."
python3 -m uvicorn integrations-hub.src.main:app --host 0.0.0.0 --port 8002 > logs/integrations-hub.log 2>&1 &
echo $! > logs/integrations-hub.pid

# 3. Finance Ledger (Port 8003)
echo "Iniciando Finance Ledger na porta 8003..."
python3 -m uvicorn finance-ledger.src.main:app --host 0.0.0.0 --port 8003 > logs/finance-ledger.log 2>&1 &
echo $! > logs/finance-ledger.pid

# 4. CRM Marketing (Port 8004)
echo "Iniciando CRM Marketing na porta 8004..."
python3 -m uvicorn crm-marketing.src.main:app --host 0.0.0.0 --port 8004 > logs/crm-marketing.log 2>&1 &
echo $! > logs/crm-marketing.pid

# 5. Compliance Governance (Port 8005)
echo "Iniciando Compliance Governance na porta 8005..."
python3 -m uvicorn compliance-governance.src.main:app --host 0.0.0.0 --port 8005 > logs/compliance-governance.log 2>&1 &
echo $! > logs/compliance-governance.pid

echo "=================================================="
echo "✅ Todos os 5 microsserviços estão rodando em background!"
echo "📁 Logs salvos na pasta 'logs/'."
echo "=================================================="
