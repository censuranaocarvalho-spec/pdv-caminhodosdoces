#!/bin/bash

PROJECT_DIR="/home/fagnersfreitas/Documentos/pdv-caminhodosdoces"
cd "$PROJECT_DIR" || exit 1

echo "🛑 Parando os microsserviços da Caminho dos Doces..."

for service in core-orders integrations-hub finance-ledger crm-marketing compliance-governance; do
    if [ -f "logs/$service.pid" ]; then
        pid=$(cat "logs/$service.pid")
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid"
            echo "Parado: $service (PID: $pid)"
        else
            echo "Serviço $service (PID: $pid) já não estava ativo."
        fi
        rm -f "logs/$service.pid"
    fi
done

echo "✨ Todos os microsserviços foram encerrados."
