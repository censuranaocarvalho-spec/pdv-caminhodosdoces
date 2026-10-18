# PDV — Caminho dos Doces

Painel único da loja: caixa, agenda, cardápio, almoxarifado, Mercado Pago, iFood e Administrativo.

## O que é este projeto

| Arquivo / pasta | Função |
| --- | --- |
| `main.py` | Servidor do PDV (porta 8090) |
| `frontend/` | Tela do navegador |
| `gerenciador.py` | Botão Ligar / Desligar (Windows) |
| `instalador/` | Instalar / iniciar / atualizar no Windows |
| `dados/` | Dados da loja (local, não vai pro Git) |
| `.github/workflows/` | Gera o zip Windows na Release |

## Como ligar (desenvolvimento)

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python main.py
```

Abra http://127.0.0.1:8090

No Windows sem Python: baixe o zip da **Release** e abra `gerenciador.exe`.
