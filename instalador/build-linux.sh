#!/usr/bin/env bash
# Empacota gerenciador + main para Linux (mesmo layout do zip Windows).
set -euo pipefail
cd "$(dirname "$0")/.."
RAIZ="$(pwd)"
PY="${RAIZ}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Falta .venv. Crie com: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

"$PY" -m pip install -q -r requirements.txt

echo "==> PyInstaller gerenciador"
"$PY" -m PyInstaller gerenciador.spec --clean --noconfirm

echo "==> PyInstaller main"
"$PY" -m PyInstaller main.spec --clean --noconfirm

OUT="${RAIZ}/dist/pdv-caminho-dos-doces"
rm -rf "$OUT"
mkdir -p "$OUT"

cp -f "${RAIZ}/dist/gerenciador" "$OUT/gerenciador"
chmod +x "$OUT/gerenciador"
cp -a "${RAIZ}/dist/main" "$OUT/main"
chmod +x "$OUT/main/main" 2>/dev/null || true

if [[ -f "${RAIZ}/versao.txt" ]]; then
  cp -f "${RAIZ}/versao.txt" "$OUT/versao.txt"
fi

cat > "$OUT/LEIA-ME.txt" <<'EOF'
Caminho dos Doces — PDV (Linux)

1. Extraia ESTE zip inteiro numa pasta (ex.: Documentos/CaminhoDosDoces).
2. Abra o terminal nessa pasta e rode: ./gerenciador
   (ou dê dois cliques em gerenciador se o sistema permitir).
3. Clique em Ligar — o PDV abre em http://127.0.0.1:8090

A pasta main/ precisa ficar ao lado do gerenciador.
Os dados da loja ficam em main/dados/ (não apague).

Pedido online (link público): no Administrativo → Dono → Licença,
configure o túnel Cloudflare e copie o link /pedir.
EOF

# Atalho .desktop (caminho relativo resolvido pelo desktop na pasta)
cat > "$OUT/Caminho dos Doces.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Caminho dos Doces
Comment=PDV — ligar e desligar
Exec=bash -c 'cd "\$(dirname "%k")" && ./gerenciador'
Path=
Icon=applications-office
Terminal=false
Categories=Office;
EOF
chmod +x "$OUT/Caminho dos Doces.desktop"

ZIP="${RAIZ}/dist/pdv-caminho-dos-doces-linux.zip"
rm -f "$ZIP"
(
  cd "${RAIZ}/dist"
  zip -rq "pdv-caminho-dos-doces-linux.zip" "pdv-caminho-dos-doces"
)

echo ""
echo "Pronto:"
echo "  Pasta: $OUT"
echo "  Zip:   $ZIP"
echo "  Rode:  $OUT/gerenciador"
