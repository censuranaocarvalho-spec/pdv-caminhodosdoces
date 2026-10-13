#!/bin/bash
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"
if [ ! -x core-orders/venv/bin/python ]; then
  python3 -m venv core-orders/venv
  core-orders/venv/bin/pip install -r core-orders/requirements.txt
fi
chmod +x "$RAIZ/instalador/iniciar.sh"
cat > "$RAIZ/instalador/Caminho dos Doces.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Caminho dos Doces
Comment=PDV da loja
Exec=/bin/bash "$RAIZ/instalador/iniciar.sh"
Path=$RAIZ
Terminal=true
Categories=Office;
EOF
chmod +x "$RAIZ/instalador/Caminho dos Doces.desktop"
echo "A loja está pronta neste computador."
echo "Para abrir: ./instalador/iniciar.sh"
echo "No navegador deste PC: http://127.0.0.1:8090"
echo "No celular, na mesma rede, use o endereço que o painel mostrar."
