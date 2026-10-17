#!/bin/bash
set -e

RAIZ="$(cd "$(dirname "$0")" && pwd)"
cd "$RAIZ"

echo "==> [1/6] Verificando Python"
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERRO: python3 nao encontrado."
  exit 1
fi
python3 --version

echo "==> [2/6] Criando/atualizando venv em core-orders/venv"
VENV="$RAIZ/core-orders/venv"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  echo "    venv criada"
else
  echo "    venv ja existe"
fi

echo "==> [3/6] Atualizando pip"
"$VENV/bin/pip" install --upgrade pip setuptools wheel --quiet

echo "==> [4/6] Instalando dependencias"
if [ -f "$RAIZ/core-orders/requirements.txt" ]; then
  "$VENV/bin/pip" install -r "$RAIZ/core-orders/requirements.txt" --quiet
fi
if [ -f "$RAIZ/requirements.txt" ]; then
  "$VENV/bin/pip" install -r "$RAIZ/requirements.txt" --quiet
fi
"$VENV/bin/pip" install --quiet \
  "fastapi>=0.115" \
  "uvicorn[standard]>=0.30" \
  "pydantic>=2.10" \
  "python-multipart>=0.0.9" \
  "psycopg2-binary>=2.9" \
  "redis>=5.0" \
  "pika>=1.3" \
  "requests>=2.32" \
  "jinja2>=3.1" \
  "httpx>=0.27"

echo "==> [5/6] Testando sintaxe do main.py"
"$VENV/bin/python" -c "import ast; ast.parse(open('main.py', encoding='utf-8').read()); print('    OK')"

echo "==> [6/6] Pronto!"
echo ""
echo "Iniciar com: ./instalador/iniciar.sh"
echo "Abrir em:   http://127.0.0.1:8090"
