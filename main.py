"""Painel do PDV Caminho dos Doces.

Igual ao outro projeto: rode e abra no navegador para ir vendo.

    .venv do core-orders:
    core-orders/venv/bin/python main.py

Painel: http://127.0.0.1:8090
"""

import base64
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import signal
import smtplib
import socket
import subprocess
import sys
import tempfile
import threading
import time
from email.message import EmailMessage
import urllib.request
import uuid
from datetime import datetime, timedelta
from html import escape
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode

import websocket

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

RAIZ = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(RAIZ, "frontend")
ARQUIVO = os.path.join(RAIZ, "dados", "pdv.json")
PASTA_RECIBOS = os.path.join(RAIZ, "dados", "recibos")
PASTA_FISICA = os.path.join(RAIZ, "dados", "pessoa-fisica")
PASTA_JURIDICA = os.path.join(RAIZ, "dados", "pessoa-juridica")
PRAZO_RECIBO_DIAS = 365
PERFIL_WHATSAPP = os.path.join(RAIZ, "dados", "whatsapp-perfil")
PORTA_WHATSAPP = 9333
JUROS_MES = 0.0199
REDES_LOJA = (
    ("WhatsApp", "https://wa.me/5561994429261"),
    ("Instagram", "https://www.instagram.com/caminhodosdoces/"),
    ("Facebook", "https://www.facebook.com/camdosdoces/"),
    ("iFood", "https://www.ifood.com.br/delivery/brasilia-df/caminho-dos-doces---biscoitos--cia-setor-oeste-sobradinho-ii/a5117093-0e88-4adf-b422-8e2985057641"),
)
ICONES_REDE = {
    "WhatsApp": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="#25D366"/><path fill="#fff" d="M12 5.4a6.6 6.6 0 0 0-5.7 9.9l-.6 2.2 2.3-.6A6.6 6.6 0 1 0 12 5.4zm3.7 9.3c-.2.5-1 .9-1.4 1-.4 0-.8.1-2.5-.6-2.1-.9-3.4-3-3.5-3.1-.1-.2-.9-1.2-.9-2.3 0-1.1.6-1.6.8-1.8.2-.2.4-.3.6-.3h.4c.2 0 .3 0 .5.4.2.5.6 1.6.7 1.7.1.2.1.3 0 .5l-.3.4c-.1.1-.2.3-.1.5.1.2.6.9 1.2 1.5.8.7 1.5.9 1.7 1 .2.1.3.1.4-.1.1-.1.5-.6.6-.8.1-.2.3-.2.5-.1.2.1 1.2.6 1.4.7.2.1.3.2.4.3.1.3 0 .8-.2 1.1z"/></svg>',
    "Instagram": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="#E1306C"/><rect x="6.2" y="6.2" width="11.6" height="11.6" rx="3.2" fill="none" stroke="#fff" stroke-width="1.4"/><circle cx="12" cy="12" r="2.7" fill="none" stroke="#fff" stroke-width="1.4"/><circle cx="15.6" cy="8.4" r=".8" fill="#fff"/></svg>',
    "Facebook": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="#1877F2"/><path fill="#fff" d="M13.4 18.2v-5.3h1.8l.3-2h-2.1V9.6c0-.6.2-1 .9-1h1.2V6.8c-.2 0-.9-.1-1.7-.1-1.7 0-2.9 1-2.9 2.9v1.3H9.2v2h1.7v5.3h2.5z"/></svg>',
    "iFood": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="#EA1D2C"/><path fill="#fff" d="M8 8.2h8.2c.4 1.4.4 2.6 0 3.6H9.4l.4 1.6h5.2c.2.8.1 1.5-.2 2.1H8.8L8 8.2zm1.2 8.8a1.1 1.1 0 1 0 0 2.2 1.1 1.1 0 0 0 0-2.2zm5.2 0a1.1 1.1 0 1 0 0 2.2 1.1 1.1 0 0 0 0-2.2z"/></svg>',
}

app = FastAPI(title="Caminho dos Doces - PDV")
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.middleware("http")
async def trancar_loja(request: Request, call_next):
    caminho = request.url.path
    livre = (
        caminho == "/"
        or caminho.startswith("/static/")
        or caminho.startswith("/api/login")
        or caminho.startswith("/redefinir")
        or caminho.startswith("/c/")
        or caminho == "/cardapio"
        or caminho.startswith("/cardapio/")
        or caminho == "/api/atualizacao"
    )
    if livre or not caminho.startswith("/api/"):
        return await call_next(request)
    token = request.cookies.get("loja") or request.headers.get("x-admin") or ""
    validade = TOKENS_ADMIN.get(token)
    if not validade or validade < time.time():
        TOKENS_ADMIN.pop(token, None)
        return JSONResponse({"detail": "Entre com o e-mail e a senha da loja."}, status_code=401)
    return await call_next(request)

PEDIDOS = []
LIVRO_CAIXA = []
CLIENTES = []
CARDAPIO = []
ALMOXARIFADO = []
TAXAS_PAGAS = []
FOLHA = []
ADMIN = {}
TOKENS_ADMIN = {}
FALHAS_SENHA = {"n": 0, "ate": 0.0}
TAREFAS = []
CAIXA = {"status": "ABERTO", "saldo": 0.0}
CARDAPIO_INICIAL = (
    ("Apliques", 4.00, 0, "a partir de"),
    ("Biscoito Amanteigado (M)", 11.00, 6, ""),
    ("Biscoito Amanteigado (G)", 16.00, 6, ""),
    ("Bombom Redondo Idade", 15.50, 0, ""),
    ("Bombom Redondo Modelagens 3D", 17.00, 0, ""),
    ("Bombom com Aplique 2D", 5.75, 0, ""),
    ("Popsicle - Brownie no Palito", 22.00, 0, "cada"),
    ("Placa de Chocolate", 14.50, 0, ""),
    ("Maçã", 13.00, 3, ""),
    ("Trufa Modelada", 17.00, 3, ""),
    ("Pirulito", 14.50, 4, ""),
    ("Porta Retrato (M)", 12.50, 0, ""),
    ("Porta Retrato (G)", 17.00, 0, ""),
    ("Bombom com Aplique 3D", 7.25, 0, "a partir de 15 unds, R$ 6,75"),
    ("Cupcakes (Mini)", 11.50, 6, ""),
    ("Cupcakes (G)", 18.00, 6, ""),
    ("Cone Recheado", 22.00, 0, ""),
    ("Palha Italiana (M)", 14.00, 4, ""),
    ("Palha Italiana (G)", 17.50, 4, ""),
    ("Casinha Palha Italiana (P)", 14.00, 3, ""),
    ("Casinha Palha Italiana (M)", 25.00, 3, ""),
    ("Casinha Palha Italiana (G)", 35.00, 3, ""),
    ("Cupcake Grande 3D", 23.50, 0, "a partir de"),
    ("Trufa Altura Dupla", 28.00, 0, ""),
    ("Moldura Grande", 17.00, 0, ""),
    ("Doces Esculturais dos Personagens", 0.0, 0, "valores são orçados separadamente"),
)


class ItemPedido(BaseModel):
    productId: str
    productName: str
    quantity: int = Field(..., gt=0)
    unitPrice: float = Field(..., gt=0)


class NovoPedido(BaseModel):
    nome: str
    telefone: str
    cpf: str = ""
    origem: str = ""
    endereco: str = ""
    cep: str = ""
    dataEvento: str = ""
    horario: str = ""
    entrega: str = ""
    observacoes: str = ""
    items: list[ItemPedido]
    pagamento: str
    parcelas: int = 1
    taxaEntrega: float = 0.0
    distanciaKm: float = 0.0
    taxaControle: float = 0.0
    valorCobrado: float = -1
    valorPrimeiraParte: float = 0.0
    cupomTipo: str = "NAO_FISCAL"


def data_do_pedido(pedido: dict) -> datetime:
    try:
        return datetime.strptime(pedido.get("criadoEm") or "", "%d/%m/%Y %H:%M")
    except ValueError:
        return datetime.now()


def nome_recibo(pedido: dict, quando: datetime) -> str:
    return f"{quando.strftime('%Y-%m-%d')}_{pedido['orderId']}"


def pasta_recibo(quando: datetime) -> str:
    return os.path.join(PASTA_RECIBOS, quando.strftime("%Y-%m"))


def apagar_recibos_antigos() -> None:
    if not os.path.isdir(PASTA_RECIBOS):
        return
    limite = datetime.now() - timedelta(days=PRAZO_RECIBO_DIAS)
    for raiz, _, arquivos in os.walk(PASTA_RECIBOS, topdown=False):
        for nome in arquivos:
            caminho = os.path.join(raiz, nome)
            dia = None
            if len(nome) >= 10 and nome[4] == "-" and nome[7] == "-":
                try:
                    dia = datetime.strptime(nome[:10], "%Y-%m-%d")
                except ValueError:
                    dia = None
            if dia is None:
                dia = datetime.fromtimestamp(os.path.getmtime(caminho))
            if dia < limite:
                os.remove(caminho)
        if raiz != PASTA_RECIBOS and not os.listdir(raiz):
            os.rmdir(raiz)


def copiar_pdf_recibo(order_id: str, origem: str) -> None:
    pedido = next((item for item in PEDIDOS if item["orderId"] == order_id), None)
    if not pedido or not os.path.isfile(origem):
        return
    quando = data_do_pedido(pedido)
    pasta = pasta_recibo(quando)
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, nome_recibo(pedido, quando) + ".pdf")
    if os.path.abspath(origem) != os.path.abspath(destino):
        shutil.copy2(origem, destino)


def carregar():
    if not os.path.exists(ARQUIVO):
        os.makedirs(PASTA_RECIBOS, exist_ok=True)
        apagar_recibos_antigos()
        return
    with open(ARQUIVO, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    PEDIDOS[:] = dados.get("pedidos", [])
    LIVRO_CAIXA[:] = dados.get("livro", [])
    CLIENTES[:] = dados.get("clientes", [])
    ALMOXARIFADO[:] = dados.get("almoxarifado", [])
    TAXAS_PAGAS[:] = dados.get("taxas", [])
    FOLHA[:] = dados.get("folha", [])
    TAREFAS[:] = dados.get("tarefas", [])
    ADMIN.clear()
    ADMIN.update(dados.get("admin") or {})
    CAIXA.update(dados.get("caixa", CAIXA))
    if "cardapio" not in dados:
        CARDAPIO[:] = cardapio_inicial()
        novo_cardapio = True
    else:
        CARDAPIO[:] = dados.get("cardapio", [])
        novo_cardapio = completar_fotos()
    if incluir_clientes_dos_pedidos() or novo_cardapio:
        descartar_pdf_cardapio()
        salvar()
    os.makedirs(PASTA_RECIBOS, exist_ok=True)
    apagar_recibos_antigos()


def salvar():
    os.makedirs(os.path.dirname(ARQUIVO), exist_ok=True)
    with open(ARQUIVO, "w", encoding="utf-8") as arquivo:
        json.dump(
            {
                "pedidos": PEDIDOS,
                "livro": LIVRO_CAIXA,
                "caixa": CAIXA,
                "clientes": CLIENTES,
                "cardapio": CARDAPIO,
                "almoxarifado": ALMOXARIFADO,
                "taxas": TAXAS_PAGAS,
                "folha": FOLHA,
                "tarefas": TAREFAS,
                "admin": ADMIN,
            },
            arquivo,
            ensure_ascii=False,
            indent=2,
        )


def cardapio_inicial() -> list[dict]:
    return [
        {
            "id": f"DOC-{indice:02d}",
            "nome": nome,
            "preco": preco,
            "minimo": minimo,
            "observacao": observacao,
            "ativo": True,
            "foto": foto_padrao(f"DOC-{indice:02d}"),
        }
        for indice, (nome, preco, minimo, observacao) in enumerate(CARDAPIO_INICIAL, start=1)
    ]


FOTOS_COMPARTILHADAS = {
    "DOC-13": "DOC-12",
    "DOC-16": "DOC-15",
    "DOC-21": "DOC-20",
    "DOC-22": "DOC-20",
}


def foto_padrao(item_id: str) -> str:
    origem = FOTOS_COMPARTILHADAS.get(item_id, item_id)
    if os.path.exists(os.path.join(FRONTEND, "fotos", f"{origem}.jpg")):
        return f"/static/fotos/{origem}.jpg"
    return "/static/fotos/generica.jpg"


def completar_fotos() -> bool:
    mudou = False
    for item in CARDAPIO:
        if item.get("foto"):
            continue
        item["foto"] = foto_padrao(item.get("id", ""))
        mudou = True
    return mudou


def preco_cardapio(item: dict) -> str:
    if float(item.get("preco") or 0) <= 0:
        return "sob orçamento"
    return dinheiro(float(item["preco"]))


def texto_minimo(item: dict) -> str:
    minimo = int(item.get("minimo") or 0)
    if minimo <= 0:
        return ""
    return f"mínimo {minimo} un"


def legenda_cardapio() -> str:
    linhas = ["Olá! Segue o cardápio da Caminho dos Doces.", ""]
    linhas.extend(f"{rotulo}: {url}" for rotulo, url in REDES_LOJA)
    return "\n".join(linhas)


def caminho_pdf_cardapio() -> str:
    return os.path.join(RAIZ, "dados", "cupons", "cardapio.pdf")


def descartar_pdf_cardapio() -> None:
    caminho = caminho_pdf_cardapio()
    if os.path.exists(caminho):
        os.remove(caminho)


def dinheiro(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ip_da_rede() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as conexao:
            conexao.connect(("8.8.8.8", 80))
            return conexao.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def base_publica(request: Request) -> str:
    host = request.headers.get("host", "127.0.0.1:8090")
    nome, _, porta = host.partition(":")
    porta = porta or "8090"
    if nome in ("127.0.0.1", "localhost", "0.0.0.0"):
        nome = ip_da_rede()
    return f"http://{nome}:{porta}"


def link_cupom(request: Request, order_id: str) -> str:
    return f"{base_publica(request)}/c/{order_id}"


def telefone_exibicao(telefone: str) -> str:
    digitos = "".join(caractere for caractere in telefone if caractere.isdigit())
    if digitos.startswith("55") and len(digitos) > 11:
        digitos = digitos[2:]
    digitos = digitos[:11]
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return telefone


def nome_e_sobrenome(nome: str) -> str:
    partes = [parte for parte in nome.split() if parte]
    if len(partes) < 2:
        raise HTTPException(status_code=400, detail="Informe o nome e o sobrenome.")
    return " ".join(partes)


def cpf_formatado(cpf: str) -> str:
    digitos = "".join(caractere for caractere in cpf if caractere.isdigit())
    if not digitos:
        return ""
    repetido = len(digitos) == 11 and digitos == digitos[0] * 11

    def digito(base: str) -> str:
        soma = sum(int(numero) * peso for numero, peso in zip(base, range(len(base) + 1, 1, -1)))
        resto = (soma * 10) % 11
        return "0" if resto == 10 else str(resto)

    invalido = (
        len(digitos) != 11
        or repetido
        or digito(digitos[:9]) != digitos[9]
        or digito(digitos[:10]) != digitos[10]
    )
    if invalido:
        raise HTTPException(
            status_code=400,
            detail="CPF inválido. Use 000.000.000-00, sem número repetido ou inventado.",
        )
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def telefone_whatsapp(telefone: str) -> str:
    digitos = "".join(caractere for caractere in telefone if caractere.isdigit())
    if digitos.startswith("55") and len(digitos) >= 12:
        return digitos
    return "55" + digitos


def legenda_redes(nome: str, cupom_tipo: str = "") -> str:
    titulo = "cupom fiscal" if (cupom_tipo or "").strip().upper() == "FISCAL" else "cupom não fiscal"
    linhas = [
        f"Olá, {nome}! Segue o {titulo} do seu pedido na Caminho dos Doces.",
        "",
    ]
    linhas.extend(f"{rotulo}: {url}" for rotulo, url in REDES_LOJA)
    return "\n".join(linhas)


def links_redes_html() -> str:
    return "".join(
        f'<a href="{escape(url)}">{ICONES_REDE.get(rotulo, "")}<span>{escape(rotulo)}</span></a>'
        for rotulo, url in REDES_LOJA
    )


def mensagem_cupom(pedido: dict, link: str) -> str:
    return legenda_redes(pedido["nome"])


def navegador_whatsapp() -> str | None:
    for nome in (
        "brave-browser",
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "microsoft-edge",
    ):
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    if os.name == "nt":
        for caminho in (
            os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        ):
            if caminho and os.path.isfile(caminho):
                return caminho
    return None


def agora_texto() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def telefone_chave(telefone: str) -> str:
    digitos = "".join(caractere for caractere in telefone if caractere.isdigit())
    if digitos.startswith("55") and len(digitos) > 11:
        return digitos[2:]
    return digitos


def nome_provisorio(nome: str, telefone: str) -> bool:
    limpo = (nome or "").strip()
    if not limpo or limpo.startswith("Contato "):
        return True
    if limpo == telefone_exibicao(telefone):
        return True
    digitos = "".join(caractere for caractere in limpo if caractere.isdigit())
    return digitos == telefone_chave(telefone) and len(digitos) >= 10


def achar_cliente(telefone: str) -> dict | None:
    chave = telefone_chave(telefone)
    if len(chave) < 10:
        return None
    for cliente in CLIENTES:
        if telefone_chave(cliente.get("telefone", "")) == chave:
            return cliente
    return None


def mesclar_contato(nome: str, telefone: str, origem: str = "WhatsApp") -> dict | None:
    chave = telefone_chave(telefone)
    if len(chave) < 10:
        return None
    exibicao = telefone_exibicao(telefone)
    nome_limpo = " ".join((nome or "").split())[:80]
    cliente = achar_cliente(telefone)
    if cliente:
        if nome_limpo and nome_provisorio(cliente.get("nome", ""), cliente.get("telefone", "")):
            cliente["nome"] = nome_limpo
        cliente["telefone"] = exibicao
        if origem and not cliente.get("origem"):
            cliente["origem"] = origem
        return cliente
    cliente = {
        "id": f"CLI-{uuid.uuid4().hex[:6].upper()}",
        "nome": nome_limpo or exibicao,
        "telefone": exibicao,
        "cpf": "",
        "origem": origem or "WhatsApp",
        "endereco": "",
        "cep": "",
        "observacoes": "",
        "organizado": False,
        "atualizadoEm": agora_texto(),
    }
    CLIENTES.append(cliente)
    return cliente


def incluir_clientes_dos_pedidos() -> bool:
    mudou = False
    for pedido in PEDIDOS:
        if not achar_cliente(pedido.get("telefone", "")):
            if mesclar_contato(pedido.get("nome", ""), pedido.get("telefone", ""), pedido.get("origem") or "Balcão"):
                mudou = True
        cliente = achar_cliente(pedido.get("telefone", ""))
        if not cliente:
            continue
        for campo in ("cpf", "endereco", "cep", "observacoes"):
            valor = (pedido.get(campo) or "").strip()
            if valor and not (cliente.get(campo) or "").strip():
                cliente[campo] = valor
                mudou = True
    return mudou


def atualizar_cliente_do_atendimento(payload: "NovoPedido") -> None:
    cliente = mesclar_contato(payload.nome, payload.telefone, payload.origem or "Balcão")
    if not cliente:
        return
    cliente["nome"] = payload.nome.strip()
    cliente["telefone"] = telefone_exibicao(payload.telefone)
    if payload.cpf.strip():
        cliente["cpf"] = payload.cpf.strip()
    if payload.endereco.strip():
        cliente["endereco"] = payload.endereco.strip()
    if payload.cep.strip():
        cliente["cep"] = payload.cep.strip()
    if payload.observacoes.strip():
        cliente["observacoes"] = payload.observacoes.strip()
    if payload.origem.strip():
        cliente["origem"] = payload.origem.strip()
    if payload.cpf.strip() or payload.endereco.strip() or payload.observacoes.strip():
        cliente["organizado"] = True
    cliente["atualizadoEm"] = agora_texto()


def porta_aberta(porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conexao:
        conexao.settimeout(0.3)
        return conexao.connect_ex(("127.0.0.1", porta)) == 0


def processos_do_perfil() -> list[tuple[int, bool]]:
    achados = []
    if not os.path.isdir("/proc"):
        return achados
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as arquivo:
                comando = arquivo.read().replace(b"\x00", b" ").decode(errors="ignore")
        except OSError:
            continue
        if PERFIL_WHATSAPP in comando and "brave" in comando or PERFIL_WHATSAPP in comando and "chrom" in comando:
            achados.append((int(pid), "--type=" in comando))
    return achados


def encerrar_perfil_whatsapp() -> None:
    for pid, filho in processos_do_perfil():
        if filho:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    for _ in range(20):
        if not any(not filho for _, filho in processos_do_perfil()):
            return
        time.sleep(0.3)
    for pid, _ in processos_do_perfil():
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    time.sleep(0.4)


def abas_whatsapp() -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORTA_WHATSAPP}/json/list", timeout=3) as resposta:
        abas = json.load(resposta)
    return [aba for aba in abas if aba.get("type") == "page" and "web.whatsapp.com" in aba.get("url", "")]


def avaliar_na_aba(aba: dict, expressao: str, aguardar: bool = True) -> object:
    conexao = websocket.create_connection(aba["webSocketDebuggerUrl"], timeout=120, suppress_origin=True)
    try:
        conexao.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": expressao, "awaitPromise": aguardar, "returnByValue": True},
        }))
        while True:
            mensagem = json.loads(conexao.recv())
            if mensagem.get("id") != 1:
                continue
            if "error" in mensagem:
                texto_erro = mensagem["error"].get("message", "") if isinstance(mensagem["error"], dict) else ""
                if "destroyed" in texto_erro or "context" in texto_erro.lower():
                    return None
                raise HTTPException(status_code=400, detail="O WhatsApp deste computador não respondeu.")
            resultado = mensagem.get("result", {})
            if "exceptionDetails" in resultado:
                print("CDP-JS", resultado["exceptionDetails"].get("text"), resultado["exceptionDetails"].get("exception", {}).get("description", "")[:300], flush=True)
                raise HTTPException(status_code=400, detail="O WhatsApp deste computador não respondeu.")
            return resultado.get("result", {}).get("value")
    finally:
        conexao.close()


def navegar_aba(aba: dict, url: str) -> None:
    conexao = websocket.create_connection(aba["webSocketDebuggerUrl"], timeout=30, suppress_origin=True)
    try:
        conexao.send(json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": url}}))
        while True:
            mensagem = json.loads(conexao.recv())
            if mensagem.get("id") == 1:
                return
    finally:
        conexao.close()


PAINEIS_LOJA = {
    "ifood": (
        "iFood",
        "https://gestordepedidos.ifood.com.br/",
        os.path.join(RAIZ, "dados", "ifood-perfil"),
    ),
    "noventa": (
        "99Food",
        "https://merchant.99app.com/pt-BR/manager",
        os.path.join(RAIZ, "dados", "noventa-perfil"),
    ),
}


def painel_loja_aberto(perfil: str) -> bool:
    if not os.path.isdir("/proc"):
        return False
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as arquivo:
                comando = arquivo.read().replace(b"\x00", b" ").decode(errors="ignore")
        except OSError:
            continue
        if perfil in comando and "--type=" not in comando and ("brave" in comando or "chrom" in comando):
            return True
    return False


def abrir_painel_loja(canal: str) -> dict:
    if canal not in PAINEIS_LOJA:
        raise HTTPException(status_code=400, detail="Escolha iFood ou 99Food.")
    nome, url, perfil = PAINEIS_LOJA[canal]
    if painel_loja_aberto(perfil):
        return {
            "aberto": True,
            "nome": nome,
            "mensagem": f"O {nome} já está aberto neste computador.",
        }
    navegador = navegador_whatsapp()
    if not navegador:
        raise HTTPException(
            status_code=400,
            detail="No computador da loja, instale o Brave ou o Chrome para o iFood e o 99Food abrirem.",
        )
    os.makedirs(perfil, exist_ok=True)
    for trava in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        caminho = os.path.join(perfil, trava)
        if os.path.lexists(caminho):
            os.remove(caminho)
    subprocess.Popen(
        [
            navegador,
            f"--user-data-dir={perfil}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--app={url}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {
        "aberto": True,
        "nome": nome,
        "mensagem": (
            f"O {nome} abriu neste computador. Na primeira vez, entre com o login da loja. "
            "A sessão fica salva, como no WhatsApp."
        ),
    }


def garantir_whatsapp(url: str) -> dict:
    navegador = navegador_whatsapp()
    if not navegador:
        raise HTTPException(
            status_code=400,
            detail="No computador da loja, instale o Brave ou o Chrome para o WhatsApp do PDV abrir.",
        )
    if not porta_aberta(PORTA_WHATSAPP):
        encerrar_perfil_whatsapp()
        os.makedirs(PERFIL_WHATSAPP, exist_ok=True)
        subprocess.Popen(
            [
                navegador,
                f"--user-data-dir={PERFIL_WHATSAPP}",
                f"--remote-debugging-port={PORTA_WHATSAPP}",
                "--remote-allow-origins=*",
                "--no-first-run",
                "--no-default-browser-check",
                f"--app={url}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    for _ in range(40):
        if porta_aberta(PORTA_WHATSAPP):
            try:
                abas = abas_whatsapp()
            except (OSError, json.JSONDecodeError, TimeoutError):
                abas = []
            if abas:
                return abas[0]
        time.sleep(0.5)
    raise HTTPException(status_code=400, detail="O WhatsApp não abriu no computador da loja.")


EXTRACAO_CONTATOS = r"""(async () => {
  const db = await new Promise((resolve, reject) => {
    const req = indexedDB.open("model-storage");
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(String(req.error));
  });
  function getAll(loja) {
    return new Promise((resolve, reject) => {
      if (!db.objectStoreNames.contains(loja)) return resolve([]);
      const tx = db.transaction(loja, "readonly");
      const req = tx.objectStore(loja).getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(String(req.error));
    });
  }
  function ser(id) {
    if (!id) return "";
    if (typeof id === "string") return id;
    if (typeof id === "object" && id._serialized) return String(id._serialized);
    return "";
  }
  function foneDe(item) {
    let digitos = String(item.phoneNumber || "").replace(/\D/g, "");
    if (digitos.length >= 10 && digitos.length <= 15) return digitos;
    const id = ser(item.id);
    if (id.endsWith("@s.whatsapp.net") || id.endsWith("@c.us")) {
      digitos = id.split("@")[0].replace(/\D/g, "");
      if (digitos.length >= 10 && digitos.length <= 15) return digitos;
    }
    return "";
  }
  const contatos = await getAll("contact");
  const chats = await getAll("chat");
  const porId = new Map(contatos.map((item) => [ser(item.id), item]));
  const escolhidos = [];
  const vistosId = new Set();
  function considerar(item) {
    if (!item) return;
    const id = ser(item.id);
    if (!id || vistosId.has(id) || id.endsWith("@g.us") || id.includes("broadcast")) return;
    vistosId.add(id);
    escolhidos.push(item);
  }
  for (const item of contatos) {
    if (item.isAddressBookContact || item.name) considerar(item);
  }
  for (const chat of chats) {
    const id = ser(chat.id);
    if (!id.endsWith("@g.us")) considerar(porId.get(id) || chat);
  }
  const saida = [];
  const vistosFone = new Set();
  for (const item of escolhidos) {
    const fone = foneDe(item);
    if (!fone || vistosFone.has(fone)) continue;
    vistosFone.add(fone);
    const nome = String(item.name || item.shortName || item.pushname || item.displayNameLID || "").replace(/\s+/g, " ").trim();
    saida.push({ nome: nome.slice(0, 80), telefone: fone });
  }
  db.close();
  return saida;
})()"""


def estado_whatsapp(aba: dict) -> dict:
    return avaliar_na_aba(
        aba,
        """(() => {
          const texto = (document.body && document.body.innerText || "").slice(0, 400);
          return {
            lista: !!document.querySelector("#pane-side"),
            baixando: texto.includes("sendo baixadas"),
            qr: texto.includes("QR Code") || texto.includes("código QR")
          };
        })()""",
        aguardar=False,
    ) or {}


def anexar_arquivo(aba: dict, pdf: str) -> None:
    conexao = websocket.create_connection(aba["webSocketDebuggerUrl"], timeout=30, suppress_origin=True)
    sequencia = 0

    def chamar(metodo: str, params: dict | None = None) -> dict:
        nonlocal sequencia
        sequencia += 1
        ident = sequencia
        conexao.send(json.dumps({"id": ident, "method": metodo, "params": params or {}}))
        while True:
            mensagem = json.loads(conexao.recv())
            if mensagem.get("id") != ident:
                continue
            if "error" in mensagem:
                print("CDP", metodo, mensagem["error"], flush=True)
                raise HTTPException(status_code=400, detail="O WhatsApp deste computador não respondeu.")
            return mensagem.get("result", {})

    try:
        chamar("DOM.enable")
        documento = chamar("DOM.getDocument", {"depth": 0})
        busca = chamar("DOM.querySelector", {
            "nodeId": documento["root"]["nodeId"],
            "selector": "input[type=file][accept='*']",
        })
        if not busca.get("nodeId"):
            raise HTTPException(status_code=400, detail="O WhatsApp não abriu o anexo do cupom.")
        chamar("DOM.setFileInputFiles", {"nodeId": busca["nodeId"], "files": [pdf]})
    finally:
        conexao.close()


def comando_cdp(aba: dict, metodo: str, params: dict | None = None) -> dict:
    conexao = websocket.create_connection(aba["webSocketDebuggerUrl"], timeout=60, suppress_origin=True)
    try:
        conexao.send(json.dumps({"id": 1, "method": metodo, "params": params or {}}))
        while True:
            mensagem = json.loads(conexao.recv())
            if mensagem.get("id") != 1:
                continue
            if "error" in mensagem:
                print("CDP", metodo, mensagem["error"], flush=True)
                raise HTTPException(status_code=400, detail="O WhatsApp deste computador não respondeu.")
            return mensagem.get("result", {})
    finally:
        conexao.close()


def caminho_pdf(order_id: str) -> str:
    return os.path.join(RAIZ, "dados", "cupons", f"{order_id}.pdf")


def gerar_pdf_da_pagina(url: str, destino: str, altura: float) -> str:
    if os.path.exists(destino) and os.path.getsize(destino) > 1000:
        return destino
    garantir_whatsapp("https://web.whatsapp.com/")
    pedido_http = urllib.request.Request(
        f"http://127.0.0.1:{PORTA_WHATSAPP}/json/new?{url}",
        method="PUT",
    )
    with urllib.request.urlopen(pedido_http, timeout=10) as resposta:
        aba = json.load(resposta)
    try:
        for _ in range(25):
            estado = avaliar_na_aba(
                aba,
                """(async () => {
                  if (document.fonts && document.fonts.ready) await document.fonts.ready;
                  const titulo = (document.querySelector('h1') || {}).textContent || '';
                  return document.readyState + '|' + titulo;
                })()""",
            )
            if isinstance(estado, str) and estado.startswith("complete") and "Caminho" in estado:
                break
            time.sleep(0.3)
        else:
            raise HTTPException(status_code=400, detail="O PDF não ficou pronto.")
        comando_cdp(aba, "Page.enable")
        impresso = comando_cdp(aba, "Page.printToPDF", {
            "printBackground": True,
            "preferCSSPageSize": False,
            "paperWidth": 4.6,
            "paperHeight": altura,
            "marginTop": 0.25,
            "marginBottom": 0.25,
            "marginLeft": 0.25,
            "marginRight": 0.25,
        })
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "wb") as arquivo:
            arquivo.write(base64.b64decode(impresso["data"]))
    finally:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{PORTA_WHATSAPP}/json/close/{aba['id']}",
                timeout=5,
            )
        except OSError:
            pass
    return destino


def gerar_pdf_cupom(order_id: str) -> str:
    if not any(pedido["orderId"] == order_id for pedido in PEDIDOS):
        raise HTTPException(status_code=404, detail="Esse cupom não existe.")
    url = f"http://127.0.0.1:{os.getenv('PORTA', '8090')}/c/{order_id}"
    caminho = gerar_pdf_da_pagina(url, caminho_pdf(order_id), 11)
    copiar_pdf_recibo(order_id, caminho)
    return caminho


def gerar_pdf_cardapio() -> str:
    if not any(item.get("ativo", True) for item in CARDAPIO):
        raise HTTPException(status_code=400, detail="O cardápio está vazio.")
    url = f"http://127.0.0.1:{os.getenv('PORTA', '8090')}/cardapio"
    return gerar_pdf_da_pagina(url, caminho_pdf_cardapio(), 18)


def enviar_pdf_no_whatsapp(aba: dict, telefone: str, texto: str, pdf: str) -> None:
    navegar_aba(aba, f"https://web.whatsapp.com/send?phone={telefone_whatsapp(telefone)}")
    pronto = False
    for _ in range(30):
        estado = avaliar_na_aba(
            aba,
            """(() => {
              const rotulos = [...document.querySelectorAll('button')].map((el) => el.getAttribute('aria-label') || '');
              const texto = (document.body && document.body.innerText || '').slice(0, 400);
              return { anexar: rotulos.includes('Anexar'), invalido: texto.includes('inválido') };
            })()""",
            aguardar=False,
        ) or {}
        if estado.get("invalido"):
            raise HTTPException(status_code=400, detail="Esse telefone não abriu conversa no WhatsApp.")
        if estado.get("anexar"):
            pronto = True
            break
        time.sleep(0.5)
    if not pronto:
        raise HTTPException(status_code=400, detail="A conversa do WhatsApp não abriu neste computador.")
    preparo = avaliar_na_aba(
        aba,
        """(async () => {
          const original = HTMLInputElement.prototype.click;
          HTMLInputElement.prototype.click = function() {};
          try {
            [...document.querySelectorAll('[aria-label="Remover anexo"]')].forEach((el) => el.click());
            if (!document.querySelector("input[type=file][accept='*']")) {
              const anexar = [...document.querySelectorAll('button')].find((el) => el.getAttribute('aria-label') === 'Anexar');
              if (!anexar) return 'sem-anexar';
              anexar.click();
              await new Promise((resolver) => setTimeout(resolver, 300));
              const documento = [...document.querySelectorAll('button')].find((el) => el.getAttribute('aria-label') === 'Documento');
              if (!documento) return 'sem-documento';
              documento.click();
              await new Promise((resolver) => setTimeout(resolver, 200));
            }
            return document.querySelector("input[type=file][accept='*']") ? 'pronto' : 'sem-input';
          } finally {
            HTMLInputElement.prototype.click = original;
          }
        })()""",
    )
    if preparo != "pronto":
        raise HTTPException(status_code=400, detail="O WhatsApp não abriu o anexo do cupom.")
    anexar_arquivo(aba, pdf)
    enviou = False
    for _ in range(20):
        time.sleep(0.3)
        if avaliar_na_aba(
            aba,
            "!!document.querySelector('[data-icon=\"wds-ic-send-filled\"]')",
            aguardar=False,
        ):
            enviou = True
            break
    if not enviou:
        raise HTTPException(status_code=400, detail="O PDF do cupom não apareceu no WhatsApp.")
    avaliar_na_aba(
        aba,
        f"""((texto) => {{
          const caixa = [...document.querySelectorAll('[contenteditable="true"]')].find((el) => {{
            const rotulo = el.getAttribute('aria-label') || '';
            return rotulo === 'Digite uma mensagem' || rotulo.startsWith('Adicione uma legenda');
          }});
          if (!caixa) return false;
          caixa.focus();
          const dados = new DataTransfer();
          dados.setData('text/plain', texto);
          caixa.dispatchEvent(new ClipboardEvent('paste', {{clipboardData: dados, bubbles: true, cancelable: true}}));
          return true;
        }})({json.dumps(texto)})""",
    )
    colado = False
    for _ in range(15):
        time.sleep(0.2)
        colado = avaliar_na_aba(
            aba,
            """(() => {
              const caixa = [...document.querySelectorAll('[contenteditable="true"]')].find((el) => {
                const rotulo = el.getAttribute('aria-label') || '';
                return rotulo === 'Digite uma mensagem' || rotulo.startsWith('Adicione uma legenda');
              });
              return !!caixa && (caixa.innerText || '').includes('http');
            })()""",
            aguardar=False,
        )
        if colado:
            break
    if not colado:
        raise HTTPException(status_code=400, detail="O link não entrou na legenda do PDF.")
    clicou = avaliar_na_aba(
        aba,
        """(() => {
          const botao = [...document.querySelectorAll('button,[role="button"],div[aria-label]')].find((el) =>
            (el.getAttribute('aria-label') || '').startsWith('Enviar')
          );
          if (botao) { botao.click(); return true; }
          const icone = document.querySelector('[data-icon="wds-ic-send-filled"]');
          const alvo = icone && (icone.closest('button') || icone.closest('[role="button"]') || icone.parentElement);
          if (!alvo) return false;
          alvo.click();
          return true;
        })()""",
        aguardar=False,
    )
    if not clicou:
        raise HTTPException(status_code=400, detail="O PDF ficou pronto no WhatsApp, mas o envio não saiu.")


def abrir_whatsapp_no_computador(telefone: str, texto: str, pedido: str = "") -> dict:
    if pedido.strip() and telefone.strip():
        pdf = gerar_pdf_cupom(pedido.strip())
        venda = next((item for item in PEDIDOS if item["orderId"] == pedido.strip()), None)
        if venda:
            texto = legenda_redes(venda["nome"], venda.get("cupomTipo") or "")
        aba = garantir_whatsapp("https://web.whatsapp.com/")
        enviar_pdf_no_whatsapp(aba, telefone, texto, pdf)
        return {"aberto": True, "pdf": True}
    if telefone.strip():
        url = f"https://web.whatsapp.com/send?phone={telefone_whatsapp(telefone)}&text={quote(texto)}"
    else:
        url = "https://web.whatsapp.com/"
    aba = garantir_whatsapp(url)
    if telefone.strip() or "web.whatsapp.com" not in aba.get("url", ""):
        navegar_aba(aba, url)
    return {"aberto": True, "pdf": False}


def importar_contatos_whatsapp() -> dict:
    aba = garantir_whatsapp("https://web.whatsapp.com/")
    estado = {}
    for _ in range(45):
        estado = estado_whatsapp(aba)
        if estado.get("lista") and not estado.get("baixando"):
            break
        time.sleep(1)
    else:
        if estado.get("qr"):
            raise HTTPException(
                status_code=409,
                detail="O WhatsApp deste computador ainda pede o QR Code. Leia com o celular da loja e clique de novo em salvar contatos.",
            )
        raise HTTPException(
            status_code=409,
            detail="O WhatsApp ainda está abrindo as conversas. Clique de novo em salvar contatos.",
        )
    brutos = avaliar_na_aba(aba, EXTRACAO_CONTATOS) or []
    if not isinstance(brutos, list) or not brutos:
        raise HTTPException(
            status_code=409,
            detail="O WhatsApp abriu, mas a lista de contatos ainda não chegou. Clique de novo em salvar contatos.",
        )
    antes = len(CLIENTES)
    for item in brutos:
        if not isinstance(item, dict):
            continue
        mesclar_contato(item.get("nome") or "", item.get("telefone") or "", "WhatsApp")
    salvar()
    return {
        "total": len(CLIENTES),
        "novos": max(len(CLIENTES) - antes, 0),
        "mensagem": (
            f"{len(CLIENTES)} contatos estão na agenda, com nome e telefone. "
            "Complete o que faltar. No atendimento, o PDV já usa esses dados."
        ),
    }


class WhatsAppAbrir(BaseModel):
    telefone: str = ""
    texto: str = ""
    pedido: str = ""


class LojaAbrir(BaseModel):
    canal: str


class ClienteAgenda(BaseModel):
    nome: str
    telefone: str
    cpf: str = ""
    endereco: str = ""
    observacoes: str = ""


class ItemCardapio(BaseModel):
    id: str = ""
    nome: str
    preco: float = 0
    minimo: int = 0
    observacao: str = ""
    ativo: bool = True
    foto: str = ""


class CardapioSalvo(BaseModel):
    itens: list[ItemCardapio]


class EnvioCardapio(BaseModel):
    telefone: str


def gravar_cardapio(itens: list[ItemCardapio]) -> list[dict]:
    saida = []
    usados = set()
    sequencia = 1
    for item in itens:
        nome = item.nome.strip()
        if not nome:
            continue
        identificador = item.id.strip()
        if not identificador or identificador in usados:
            while True:
                identificador = f"DOC-{sequencia:02d}"
                sequencia += 1
                if identificador not in usados:
                    break
        usados.add(identificador)
        saida.append({
            "id": identificador,
            "nome": nome,
            "preco": round(max(item.preco, 0), 2),
            "minimo": max(int(item.minimo), 0),
            "observacao": item.observacao.strip(),
            "ativo": bool(item.ativo),
            "foto": item.foto.strip() or foto_padrao(identificador),
        })
    CARDAPIO[:] = saida
    descartar_pdf_cardapio()
    salvar()
    return saida


def pagina_cardapio() -> str:
    blocos = []
    for item in CARDAPIO:
        if not item.get("ativo", True):
            continue
        detalhe = " · ".join(parte for parte in (texto_minimo(item), item.get("observacao") or "") if parte)
        extra = f"<small>{escape(detalhe)}</small>" if detalhe else ""
        foto = item.get("foto") or foto_padrao(item.get("id", ""))
        blocos.append(
            f"<div class='item'><img src='{escape(foto)}' alt='{escape(item['nome'])}'>"
            f"<span class='nome'>{escape(item['nome'])}{extra}</span>"
            f"<span class='preco'>{escape(preco_cardapio(item))}</span></div>"
        )
    lista = "".join(blocos) or "<div>Nenhum item no cardápio.</div>"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cardápio — Caminho dos Doces</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    body {{ margin: 0; background: #FFFBFC; color: #7C4A3A; font-family: Poppins, Verdana, sans-serif; overflow-y: auto; }}
    main {{ max-width: 440px; margin: 24px auto; background: #fff; border: 1px solid #C5CEE6; border-radius: 16px; padding: 18px; }}
    h1 {{ text-align: center; font-size: 20px; margin: 8px 0 4px; }}
    .centro {{ text-align: center; font-size: 13px; }}
    .logo {{ width: 96px; height: 96px; border-radius: 50%; object-fit: cover; border: 3px solid #7C4A3A; display: block; margin: 0 auto; }}
    hr {{ border: none; border-top: 1px dashed #7C4A3A; margin: 12px 0; }}
    .item {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #F3E7EA; }}
    .item img {{ width: 92px; height: 92px; object-fit: cover; border-radius: 16px; border: 3px solid #C2E5E9; background: #fff; }}
    .item .nome {{ flex: 1; font-weight: 600; }}
    .item small {{ display: block; font-weight: 400; font-size: 12px; }}
    .item .preco {{ white-space: nowrap; font-weight: 600; }}
    a {{ color: #7C4A3A; font-weight: 600; text-decoration: none; }}
    .convite {{ font-size: 12px; margin: 10px 0 0; }}
    .redes {{ display: flex; justify-content: center; align-items: flex-start; gap: 16px; flex-wrap: wrap; margin: 8px 0 0; }}
    .redes a {{ display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 11px; }}
    .redes svg {{ width: 40px; height: 40px; display: block; }}
  </style>
</head>
<body>
  <main>
    <img class="logo" src="/static/logo.png" alt="Caminho dos Doces">
    <h1>Caminho dos Doces</h1>
    <div class="centro">CARDÁPIO<br>CNPJ 46.415.117/0001-37<br>AR 05 Conjunto 01 casa 16<br>(61) 99442-9261</div>
    <hr>
    {lista}
    <p class="centro">Documento sem valor fiscal.</p>
    <p class="centro convite">Toque nos ícones para conhecer nossas redes.</p>
    <p class="redes">{links_redes_html()}</p>
  </main>
</body>
</html>"""


def links_envio(pedido: dict, link: str) -> dict:
    texto = quote(mensagem_cupom(pedido, link))
    return {
        "link": link,
        "whatsapp": f"https://web.whatsapp.com/send?phone={telefone_whatsapp(pedido['telefone'])}&text={texto}",
        "mensagem": mensagem_cupom(pedido, link),
    }


ENTREGAS_DA_LOJA = {"Motoboy da loja", "Entrega particular"}
TAXA_MINIMA = 10.0
KM_INCLUSOS = 5.0


LOJA_LAT = -15.6387929
LOJA_LNG = -47.8253293
LOJA_ORIGEM = "AR 05 Conjunto 01 casa 16, Setor Oeste, Sobradinho II, Brasília-DF"
CENTRO_BRASILIA = (-15.77972, -47.92972)


def baixar_json(url: str, timeout: int = 8) -> dict | list:
    pedido = urllib.request.Request(url, headers={"User-Agent": "CaminhoDosDoces-PDV/1.0 (entrega)"})
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        return json.load(resposta)


def coordenada_util(lat: float, lng: float) -> bool:
    return abs(lat - CENTRO_BRASILIA[0]) > 0.02 or abs(lng - CENTRO_BRASILIA[1]) > 0.02


def montar_endereco(partes: list[str]) -> str:
    return ", ".join(parte.strip() for parte in partes if parte and parte.strip())


def coordenadas_do_cep(cep: str) -> tuple[float, float, str]:
    try:
        dados = baixar_json(f"https://cep.awesomeapi.com.br/json/{cep}")
        lat = float(dados.get("lat") or 0)
        lng = float(dados.get("lng") or 0)
        if lat and lng and coordenada_util(lat, lng):
            endereco = montar_endereco([
                dados.get("address", ""),
                dados.get("district", ""),
                dados.get("city", ""),
                dados.get("state", ""),
                f"{cep[:5]}-{cep[5:]}",
            ])
            return lat, lng, endereco
    except HTTPError as erro:
        if erro.code not in (404, 400):
            raise
    except (URLError, TimeoutError, ValueError, KeyError):
        pass

    via = baixar_json(f"https://viacep.com.br/ws/{cep}/json/")
    if not isinstance(via, dict) or via.get("erro"):
        raise HTTPException(status_code=404, detail="CEP não encontrado. Informe a distância em km.")
    endereco = montar_endereco([
        via.get("logradouro", ""),
        via.get("bairro", ""),
        via.get("localidade", ""),
        via.get("uf", ""),
        via.get("cep", ""),
    ])
    consulta = montar_endereco([
        via.get("logradouro", ""),
        via.get("bairro", ""),
        via.get("localidade", ""),
        via.get("uf", ""),
        "Brasil",
    ])
    busca = baixar_json(
        "https://nominatim.openstreetmap.org/search?"
        + urlencode({"q": consulta, "format": "json", "limit": 1, "countrycodes": "br"})
    )
    if not isinstance(busca, list) or not busca:
        raise HTTPException(status_code=404, detail="CEP encontrado, mas sem ponto no mapa. Informe a distância em km.")
    lat = float(busca[0]["lat"])
    lng = float(busca[0]["lon"])
    if not coordenada_util(lat, lng):
        raise HTTPException(status_code=404, detail="Não achei o ponto desse CEP. Informe a distância em km.")
    return lat, lng, endereco


def km_de_carro(lat: float, lng: float) -> float:
    rota = baixar_json(
        f"https://router.project-osrm.org/route/v1/driving/{LOJA_LNG},{LOJA_LAT};{lng},{lat}?overview=false"
    )
    metros = float(rota["routes"][0]["distance"])
    return round(math.ceil(metros / 100) / 10, 1)


def calcular_taxa_entrega(entrega: str, km: float) -> float:
    if entrega not in ENTREGAS_DA_LOJA:
        return 0.0
    extra = max(float(km or 0) - KM_INCLUSOS, 0)
    return (int(TAXA_MINIMA * 100) + int(round(extra * 180))) / 100


def pedido_publico(request: Request, pedido: dict) -> dict:
    copia = dict(pedido)
    copia["link"] = link_cupom(request, pedido["orderId"])
    copia["pdf"] = f"{copia['link']}/pdf"
    return copia


def fechar_pagamento(payload: NovoPedido, base: float) -> dict:
    metodo = payload.pagamento
    parcelas = payload.parcelas or 1

    if metodo in ("PIX", "DINHEIRO"):
        sinal = round(base * 0.5, 2)
        restante = round(base - sinal, 2)
        nome = "PIX" if metodo == "PIX" else "Dinheiro"
        return {
            "total": base,
            "sinal": sinal,
            "restante": restante,
            "descricao": f"{nome} — 50% agora",
            "statusPagamento": "AGUARDANDO_RESTANTE",
            "partes": [{"forma": nome, "valor": sinal}],
            "lembrete": f"LEMBRETE: a cliente ainda precisa pagar os outros 50% ({dinheiro(restante)}) na entrega.",
            "juros": "",
        }

    integrais = {
        "DINHEIRO_INTEGRAL": "Dinheiro integral",
        "DEBITO_INTEGRAL": "Débito integral",
        "PIX_INTEGRAL": "PIX integral",
    }
    if metodo in integrais:
        return {
            "total": base,
            "sinal": base,
            "restante": 0.0,
            "descricao": integrais[metodo],
            "statusPagamento": "PAGO",
            "partes": [{"forma": integrais[metodo], "valor": base}],
            "lembrete": "",
            "juros": "",
        }

    if metodo == "CREDITO":
        if parcelas < 1 or parcelas > 5:
            raise HTTPException(status_code=400, detail="No crédito, o máximo é 5 vezes.")
        total = base
        juros = ""
        if parcelas > 1:
            total = round(base * (1 + JUROS_MES * parcelas), 2)
            juros = "Juros do parcelamento por conta da cliente."
        vezes = "à vista" if parcelas == 1 else f"{parcelas}x"
        return {
            "total": total,
            "sinal": total,
            "restante": 0.0,
            "descricao": f"Cartão de crédito ({vezes})",
            "statusPagamento": "PAGO",
            "partes": [{"forma": f"Crédito {vezes}", "valor": total}],
            "lembrete": "",
            "juros": juros,
        }

    mistos = {
        "CREDITO_DINHEIRO": ("Dinheiro", "Crédito"),
        "CREDITO_PIX": ("PIX", "Crédito"),
        "DINHEIRO_PIX": ("Dinheiro", "PIX"),
    }
    if metodo not in mistos:
        raise HTTPException(status_code=400, detail="Forma de pagamento não reconhecida.")

    forma_a, forma_b = mistos[metodo]
    valor_a = round(payload.valorPrimeiraParte, 2)
    if valor_a <= 0 or valor_a >= base:
        raise HTTPException(
            status_code=400,
            detail=f"Informe o valor em {forma_a.lower()} maior que zero e menor que o total.",
        )
    valor_b = round(base - valor_a, 2)
    juros = ""
    if forma_b == "Crédito" and parcelas > 1:
        if parcelas > 5:
            raise HTTPException(status_code=400, detail="No crédito, o máximo é 5 vezes.")
        valor_b = round(valor_b * (1 + JUROS_MES * parcelas), 2)
        forma_b = f"Crédito {parcelas}x"
        juros = "Juros do parcelamento por conta da cliente, só sobre a parte do cartão."
    elif forma_b == "Crédito":
        forma_b = "Crédito à vista"

    total = round(valor_a + valor_b, 2)
    return {
        "total": total,
        "sinal": total,
        "restante": 0.0,
        "descricao": f"{forma_a} + {forma_b}",
        "statusPagamento": "PAGO",
        "partes": [{"forma": forma_a, "valor": valor_a}, {"forma": forma_b, "valor": valor_b}],
        "lembrete": "",
        "juros": juros,
    }


carregar()


@app.get("/")
def painel():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


def dia_operacao(quando: datetime | None = None) -> datetime:
    quando = quando or datetime.now()
    if quando.hour < 8:
        return quando - timedelta(days=1)
    return quando


def _dia_gravado(texto: str) -> datetime | None:
    try:
        return datetime.strptime((texto or "")[:16], "%d/%m/%Y %H:%M")
    except ValueError:
        return None


def marca_no_dia(chave: str) -> bool:
    quando = _dia_gravado(ADMIN.get(chave) or "")
    if not quando:
        return False
    return dia_operacao(quando).date() == dia_operacao().date()


def saldos_atualizados() -> bool:
    return marca_no_dia("saldosEm")


def canal_hoje(chave: str) -> bool:
    if chave in ADMIN:
        return marca_no_dia(chave)
    return marca_no_dia("saldosEm")


def gaveta_conferida() -> bool:
    quando = _dia_gravado(CAIXA.get("gavetaEm") or "")
    if not quando:
        return False
    return dia_operacao(quando).date() == dia_operacao().date()


def tres_conferidos() -> bool:
    return canal_hoje("ifoodVendasEm") and canal_hoje("noventaVendasEm") and canal_hoje("bancoVendasEm") and gaveta_conferida()


def falta_conferencia() -> str:
    if not canal_hoje("ifoodVendasEm"):
        return "ifood"
    if not canal_hoje("noventaVendasEm"):
        return "noventa"
    if not canal_hoje("bancoVendasEm"):
        return "banco"
    if not gaveta_conferida():
        return "gaveta"
    return ""


def cardapio_conferido() -> bool:
    quando = _dia_gravado(CAIXA.get("cardapioEm") or "")
    if not quando:
        return False
    return dia_operacao(quando).date() == dia_operacao().date()


def hora_de_fechar() -> bool:
    agora = datetime.now()
    if agora.hour < 8:
        return True
    return (agora.hour, agora.minute) >= (22, 30)


def pedir_estoque(order_id: str) -> None:
    if any(tarefa["orderId"] == order_id and tarefa["tipo"] == "ESTOQUE" and not tarefa.get("feitoEm") for tarefa in TAREFAS):
        return
    TAREFAS.append({
        "id": f"RB-{uuid.uuid4().hex[:6].upper()}",
        "tipo": "ESTOQUE",
        "orderId": order_id,
        "criadoEm": agora_texto(),
        "feitoEm": "",
    })


def alertas_robo() -> list:
    alertas = []
    estoques = [tarefa for tarefa in TAREFAS if tarefa["tipo"] == "ESTOQUE" and not tarefa.get("feitoEm")]
    if estoques:
        antiga = estoques[0]
        quantidade = len(estoques)
        texto = (
            f"O cupom não fiscal {antiga['orderId']} já saiu. Abra o depósito e marque o que essa venda usou. "
            "Conferir na hora evita juntar várias vendas e corrigir tudo de uma vez."
        )
        if quantidade > 1:
            texto += f" Comece pela mais antiga. Falta conferir {quantidade}."
        alertas.append({
            "tipo": "ESTOQUE",
            "orderId": antiga["orderId"],
            "titulo": "Confira o estoque desta venda" if quantidade == 1 else f"Confira o estoque de {quantidade} vendas",
            "texto": texto,
            "quantidade": quantidade,
        })
    if CAIXA.get("status") == "ABERTO" and hora_de_fechar() and not tres_conferidos():
        alertas.append({
            "tipo": "SALDOS",
            "orderId": "",
            "titulo": "Falta o valor de vendas para fechar o caixa",
            "texto": (
                "O botão vermelho mostra o que falta, nesta ordem: valor de vendas do iFood, valor de vendas do 99Food, banco e a contagem da gaveta. "
                "Ela digita o valor, aperta Enter, salva e segue para o próximo. "
                "Com tudo salvo, o botão fica verde. Conferir e fechar encerra o caixa."
            ),
            "quantidade": 3,
        })
    if not cardapio_conferido():
        alertas.append({
            "tipo": "CARDAPIO",
            "orderId": "",
            "titulo": "Ao abrir o PDV, confira o cardápio",
            "texto": (
                "O cardápio da loja, o estoque do iFood e o estoque do 99Food entram juntos. "
                "Confira se a loja está com todos os itens e se os dois aplicativos mostram o que a cozinha tem. "
                "Conferir na abertura deixa o dia inteiro vendendo o que existe."
            ),
            "quantidade": 3,
        })
    return alertas


ELOGIO_CARDAPIO = {
    "titulo": "Muito bem",
    "texto": (
        "Cardápio conferido. A loja, o iFood e o 99Food estão com os mesmos itens. "
        "O dia começa alinhado com a vitrine e a cozinha."
    ),
}

ELOGIO_CAIXA = {
    "titulo": "Boa noite",
    "texto": (
        "Caixa encerrado. O valor de vendas do iFood, do 99Food e o banco de hoje foram conferidos e salvos. "
        "Até amanhã."
    ),
}


TAMANHO_CICLO = {
    "ifood": {"NENHUMA": 30, "SEMANAL": 7, "SEMANAL_DIGITAL": 7, "SOB_DEMANDA": 1},
    "noventa": {"NENHUMA": 7, "SEMANAL": 7, "DIARIO": 1},
}
NOME_CICLO = {
    "ifood": {
        "NENHUMA": "Repasse em 30 dias",
        "SEMANAL": "Repasse semanal",
        "SEMANAL_DIGITAL": "Repasse semanal na Conta Digital",
        "SOB_DEMANDA": "Repasse em 1 dia",
    },
    "noventa": {
        "NENHUMA": "Ciclo de 7 dias, sem taxa de saque",
        "SEMANAL": "Repasse semanal",
        "DIARIO": "Repasse diário",
    },
}


def _data_curta(texto: str):
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:
        return None


def montar_ciclo(dias: list, tipo: str, canal: str, inicio_texto: str) -> dict:
    tamanho = TAMANHO_CICLO[canal].get(tipo, 7)
    hoje = dia_operacao().date()
    inicio = _data_curta(inicio_texto or "") or hoje
    if hoje < inicio:
        inicio = hoje
    bloco = max((hoje - inicio).days, 0) // tamanho
    comeco = inicio + timedelta(days=bloco * tamanho)
    fim = comeco + timedelta(days=tamanho - 1)
    atuais = []
    anteriores = 0.0
    for item in dias or []:
        if not isinstance(item, dict):
            continue
        data = _data_curta(item.get("dia") or "")
        if not data:
            continue
        liquido = float(item.get("liquido") or 0)
        if comeco <= data <= fim:
            atuais.append({"dia": item["dia"], "bruto": float(item.get("bruto") or 0), "liquido": liquido})
        elif data < comeco:
            anteriores = round(anteriores + liquido, 2)
    atuais.sort(key=lambda item: _data_curta(item["dia"]))
    return {
        "nome": NOME_CICLO[canal].get(tipo, "Repasse"),
        "tamanho": tamanho,
        "inicio": comeco.strftime("%d/%m/%Y"),
        "fim": fim.strftime("%d/%m/%Y"),
        "dias": atuais,
        "bruto": round(sum(item["bruto"] for item in atuais), 2),
        "liquido": round(sum(item["liquido"] for item in atuais), 2),
        "anteriores": anteriores,
    }


def registrar_venda_dia(lista_chave: str, em_chave: str, inicio_chave: str, tipo_chave: str, tipo: str, conta: dict) -> None:
    hoje = dia_operacao().strftime("%d/%m/%Y")
    dias = [item for item in (ADMIN.get(lista_chave) or []) if isinstance(item, dict) and item.get("dia") != hoje]
    dias.append({
        "dia": hoje,
        "bruto": conta["bruto"],
        "liquido": round(conta["bruto"] - conta["juros"], 2),
    })
    ADMIN[lista_chave] = dias
    ADMIN[em_chave] = agora_texto()
    if not ADMIN.get(inicio_chave) or ADMIN.get(tipo_chave) != tipo:
        ADMIN[inicio_chave] = hoje
        ADMIN[tipo_chave] = tipo


def garantir_conferencia_antiga() -> bool:
    if "ifoodVendasEm" in ADMIN or "noventaVendasEm" in ADMIN or "bancoVendasEm" in ADMIN:
        return False
    origem = ADMIN.get("saldosEm") or ""
    if not _dia_gravado(origem):
        return False
    dia = dia_operacao(_dia_gravado(origem)).strftime("%d/%m/%Y")
    ifood = conta_ifood(ADMIN)
    noventa = conta_noventa(ADMIN)
    ADMIN["ifoodVendasEm"] = origem
    ADMIN["noventaVendasEm"] = origem
    ADMIN["bancoVendasEm"] = origem
    ADMIN["ifoodDias"] = [{"dia": dia, "bruto": ifood["bruto"], "liquido": round(ifood["bruto"] - ifood["juros"], 2)}]
    ADMIN["noventaDias"] = [{"dia": dia, "bruto": noventa["bruto"], "liquido": round(noventa["bruto"] - noventa["juros"], 2)}]
    ADMIN["ifoodCicloInicio"] = dia
    ADMIN["ifoodCicloTipo"] = ADMIN.get("ifoodAntecipacao") or "NENHUMA"
    ADMIN["noventaCicloInicio"] = dia
    ADMIN["noventaCicloTipo"] = ADMIN.get("noventaRepasse") or "NENHUMA"
    return True


@app.get("/api/caixa")
def caixa():
    return CAIXA


class FecharCaixa(BaseModel):
    ifood: bool = False
    noventa: bool = False
    banco: bool = False


class CupomRobo(BaseModel):
    orderId: str


class ConferirCardapio(BaseModel):
    cardapio: bool = False
    ifood: bool = False
    noventa: bool = False


@app.get("/api/robo")
def ler_robo():
    ifood = conta_ifood(ADMIN)
    noventa = conta_noventa(ADMIN)
    return {
        "alertas": alertas_robo(),
        "saldosHoje": saldos_atualizados(),
        "cardapioHoje": cardapio_conferido(),
        "ifoodHoje": canal_hoje("ifoodVendasEm"),
        "noventaHoje": canal_hoje("noventaVendasEm"),
        "bancoHoje": canal_hoje("bancoVendasEm"),
        "gavetaHoje": gaveta_conferida(),
        "ifoodDias": ADMIN.get("ifoodDias") or [],
        "noventaDias": ADMIN.get("noventaDias") or [],
        "ifoodCiclo": montar_ciclo(ADMIN.get("ifoodDias") or [], ifood["antecipacao"], "ifood", ADMIN.get("ifoodCicloInicio") or ""),
        "noventaCiclo": montar_ciclo(ADMIN.get("noventaDias") or [], noventa["repasse"], "noventa", ADMIN.get("noventaCicloInicio") or ""),
        "caixa": CAIXA["status"],
    }


@app.post("/api/robo/cardapio")
def conferir_cardapio_do_dia(payload: ConferirCardapio):
    if not (payload.cardapio and payload.ifood and payload.noventa):
        raise HTTPException(
            status_code=400,
            detail="Marque os três: cardápio da loja, estoque do iFood e estoque do 99Food.",
        )
    CAIXA["cardapioEm"] = agora_texto()
    salvar()
    return {"alertas": alertas_robo(), "cardapioHoje": True, "elogio": ELOGIO_CARDAPIO}


@app.post("/api/robo/cupom")
def robo_cupom(payload: CupomRobo):
    if not any(pedido["orderId"] == payload.orderId for pedido in PEDIDOS):
        raise HTTPException(status_code=404, detail="Essa venda não está no caixa.")
    pedir_estoque(payload.orderId)
    salvar()
    return {"alertas": alertas_robo()}


@app.post("/api/robo/estoque/{order_id}")
def conferir_estoque(order_id: str):
    tarefa = next(
        (item for item in TAREFAS if item["orderId"] == order_id and item["tipo"] == "ESTOQUE" and not item.get("feitoEm")),
        None,
    )
    if not tarefa:
        raise HTTPException(status_code=404, detail="Essa venda já foi conferida.")
    tarefa["feitoEm"] = agora_texto()
    salvar()
    return {"alertas": alertas_robo()}


@app.post("/api/caixa/fechar")
def fechar_caixa(payload: FecharCaixa):
    if CAIXA["status"] != "ABERTO":
        raise HTTPException(status_code=400, detail="O caixa já está fechado.")
    if not (payload.ifood and payload.noventa and payload.banco):
        raise HTTPException(status_code=400, detail="Marque o iFood, o 99Food e o banco. Os três entram no fechamento.")
    falta = falta_conferencia()
    if falta:
        raise HTTPException(status_code=400, detail={"mensagem": "Salve o valor de vendas do iFood, do 99Food e o banco antes de fechar.", "falta": falta})
    CAIXA["status"] = "FECHADO"
    CAIXA["fechadoEm"] = agora_texto()
    salvar()
    return {"caixa": CAIXA, "alertas": alertas_robo(), "elogio": ELOGIO_CAIXA}


@app.post("/api/caixa/conferir")
def conferir_caixa():
    if CAIXA["status"] != "ABERTO":
        raise HTTPException(status_code=400, detail="O caixa já está fechado.")
    mensagens = {
        "ifood": "Falta salvar o valor de vendas do iFood. Digite o valor, aperte Enter e salve na aba Banco.",
        "noventa": "Falta salvar o valor de vendas do 99Food. Digite o valor, aperte Enter e salve na aba Banco.",
        "banco": "Falta salvar o banco. Atualize a conta empresa e o Nubank e salve na aba Banco.",
        "gaveta": "Falta contar a gaveta. Digite o dinheiro contado e salve no Financeiro.",
    }
    falta = falta_conferencia()
    if falta:
        raise HTTPException(status_code=400, detail={"mensagem": mensagens[falta], "falta": falta})
    CAIXA["status"] = "FECHADO"
    CAIXA["fechadoEm"] = agora_texto()
    salvar()
    return {"caixa": CAIXA, "alertas": alertas_robo(), "elogio": ELOGIO_CAIXA}


class ContagemGaveta(BaseModel):
    contado: float = 0


class PassagemBanco(BaseModel):
    valor: float


@app.post("/api/caixa/gaveta")
def conferir_gaveta(payload: ContagemGaveta):
    if payload.contado < 0:
        raise HTTPException(status_code=400, detail="A contagem não pode ser negativa.")
    contado = round(payload.contado, 2)
    saldo = round(float(CAIXA.get("saldo") or 0), 2)
    CAIXA["gavetaContado"] = contado
    CAIXA["gavetaEm"] = agora_texto()
    salvar()
    return {
        "saldo": saldo,
        "contado": contado,
        "diferenca": round(contado - saldo, 2),
        "gavetaHoje": True,
        "caixa": CAIXA,
    }


@app.post("/api/caixa/banco")
def passar_para_banco(payload: PassagemBanco):
    if CAIXA["status"] != "ABERTO":
        raise HTTPException(status_code=400, detail="Abra o caixa para passar dinheiro ao banco.")
    valor = round(payload.valor, 2)
    saldo = round(float(CAIXA.get("saldo") or 0), 2)
    if valor <= 0:
        raise HTTPException(status_code=400, detail="Informe o valor que sai da gaveta.")
    if valor > saldo:
        raise HTTPException(status_code=400, detail=f"A gaveta tem {dinheiro(saldo)}.")
    CAIXA["saldo"] = round(saldo - valor, 2)
    ADMIN["empresaSaldo"] = round(float(ADMIN.get("empresaSaldo") or 0) + valor, 2)
    CAIXA["gavetaEm"] = ""
    LIVRO_CAIXA.append({
        "id": f"CX-{uuid.uuid4().hex[:6].upper()}",
        "orderId": "",
        "descricao": "Passei da gaveta para a conta empresa",
        "tipo": "SAIDA",
        "categoria": "BANCO",
        "valor": valor,
        "criadoEm": agora_texto(),
    })
    salvar()
    return {"caixa": CAIXA, "empresaSaldo": ADMIN["empresaSaldo"], "valor": valor}


@app.post("/api/caixa/abrir")
def abrir_caixa_do_dia():
    CAIXA["status"] = "ABERTO"
    CAIXA["abertoEm"] = agora_texto()
    salvar()
    return {"caixa": CAIXA, "alertas": alertas_robo()}


@app.get("/api/pedidos")
def listar_pedidos(request: Request):
    return [pedido_publico(request, pedido) for pedido in reversed(PEDIDOS)]


def tipo_de_cupom(valor: str) -> str:
    return "FISCAL" if (valor or "").strip().upper() == "FISCAL" else "NAO_FISCAL"


def emissao_fiscal_disponivel() -> bool:
    return False


def cabecalho_cupom(pedido: dict) -> str:
    loja = "CNPJ 46.415.117/0001-37<br>AR 05 Conjunto 01 casa 16<br>(61) 99442-9261"
    if tipo_de_cupom(pedido.get("cupomTipo") or "") == "FISCAL":
        return f"CUPOM FISCAL<br>Número, série e chave aguardam o módulo fiscal<br>{loja}"
    return f"CUPOM NÃO FISCAL<br>{loja}"


def rodape_cupom(pedido: dict) -> str:
    if tipo_de_cupom(pedido.get("cupomTipo") or "") == "FISCAL":
        return (
            "Esta venda ficou marcada para cupom fiscal. "
            "O botão de emitir continua desligado. Documento ainda sem valor fiscal."
        )
    linha = texto_impressora()
    if linha:
        return f"Documento sem valor fiscal.<br>{escape(linha)}"
    return "Documento sem valor fiscal."


def pagina_cupom(pedido: dict, link: str) -> str:
    itens = "".join(
        f"<div class='item'><span>{escape(str(item['quantity']))}× {escape(item['productName'])}</span>"
        f"<span>{escape(dinheiro(item['quantity'] * item['unitPrice']))}</span></div>"
        for item in pedido["items"]
    )
    partes = "".join(
        f"<div>{escape(parte['forma'])}: {escape(dinheiro(parte['valor']))}</div>"
        for parte in pedido.get("partes", [])
    )
    lembrete = (
        f"<div class='lembrete'>{escape(pedido['lembrete'])}</div>"
        if pedido.get("lembrete")
        else "<div>Pagamento quitado. Nada pendente na entrega.</div>"
    )
    juros = f"<div class='nota'>{escape(pedido['juros'])}</div>" if pedido.get("juros") else ""
    resultado = float(pedido.get("resultado") or 0)
    desconto = ""
    if resultado < 0:
        desconto = f"<div class='item'><span>Desconto</span><span>- {escape(dinheiro(abs(resultado)))}</span></div>"
    entrega = ""
    if pedido.get("dataEvento") or pedido.get("endereco") or pedido.get("entrega"):
        km = pedido.get("distanciaKm") or 0
        trecho_km = f" · {str(km).replace('.', ',')} km" if km else ""
        entrega = (
            f"<div>Entrega: {escape(pedido.get('dataEvento', ''))} {escape(pedido.get('horario', ''))}"
            f" · {escape(pedido.get('entrega', ''))}{escape(trecho_km)}</div>"
            f"<div>{escape(pedido.get('endereco', ''))}</div>"
        )
    if pedido.get("taxaControle"):
        entrega += (
            f"<div class='nota'>Corrida paga pela cliente: {escape(dinheiro(pedido['taxaControle']))}. "
            "Não entra neste total.</div>"
        )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cupom {escape(pedido['orderId'])} — Caminho dos Doces</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    body {{ margin: 0; background: #FFFBFC; color: #7C4A3A; font-family: Poppins, Verdana, sans-serif; overflow-y: auto; }}
    main {{ max-width: 440px; margin: 24px auto; background: #fff; border: 1px solid #C5CEE6; border-radius: 16px; padding: 18px; }}
    h1 {{ text-align: center; font-size: 20px; margin: 8px 0 4px; }}
    .centro {{ text-align: center; font-size: 13px; }}
    .logo {{ width: 96px; height: 96px; border-radius: 50%; object-fit: cover; border: 3px solid #7C4A3A; display: block; margin: 0 auto; }}
    hr {{ border: none; border-top: 1px dashed #7C4A3A; margin: 12px 0; }}
    .item {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; padding: 6px 0; }}
    .item span:first-child {{ flex: 1; }}
    .item span:last-child {{ white-space: nowrap; }}
    .lembrete {{ background: #FDE8EF; border: 1px solid #F0BCCF; border-radius: 8px; padding: 8px; font-weight: 600; }}
    .nota {{ background: #F4FBFC; border-left: 4px solid #C2E5E9; padding: 8px; margin-top: 8px; }}
    a {{ color: #7C4A3A; font-weight: 600; text-decoration: none; }}
    .convite {{ font-size: 12px; margin: 10px 0 0; }}
    .redes {{ display: flex; justify-content: center; align-items: flex-start; gap: 16px; flex-wrap: wrap; margin: 8px 0 0; }}
    .redes a {{ display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 11px; }}
    .redes svg {{ width: 40px; height: 40px; display: block; }}
  </style>
</head>
<body>
  <main>
    <img class="logo" src="/static/logo.png" alt="Caminho dos Doces">
    <h1>Caminho dos Doces</h1>
    <div class="centro">{cabecalho_cupom(pedido)}</div>
    <hr>
    <div>{escape(pedido['orderId'])} · {escape(pedido['criadoEm'])}</div>
    <div><strong>{escape(pedido['nome'])}</strong><br>{escape(telefone_exibicao(pedido['telefone']))}</div>
    {entrega}
    <hr>
    {itens}
    <div class="item"><span>Entrega</span><span>{escape(dinheiro(pedido['taxaEntrega']))}</span></div>
    {desconto}
    <div class="item"><strong>Total</strong><strong>{escape(dinheiro(pedido['total']))}</strong></div>
    <hr>
    <div>{escape(pedido['pagamento'])}</div>
    {partes}
    {juros}
    <div class="item"><span>Pago agora</span><strong>{escape(dinheiro(pedido['sinal']))}</strong></div>
    {lembrete}
    <p class="centro">{rodape_cupom(pedido)}</p>
    <p class="centro convite">Toque nos ícones para conhecer nossas redes.</p>
    <p class="redes">{links_redes_html()}</p>
  </main>
</body>
</html>"""


def salvar_recibo(pedido: dict) -> str:
    quando = data_do_pedido(pedido)
    pasta = pasta_recibo(quando)
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, nome_recibo(pedido, quando) + ".html")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(pagina_cupom(pedido, f"/c/{pedido['orderId']}"))
    apagar_recibos_antigos()
    return caminho


@app.get("/c/{order_id}/pdf")
def cupom_pdf(order_id: str):
    caminho = gerar_pdf_cupom(order_id)
    return FileResponse(caminho, media_type="application/pdf", filename=f"Cupom-{order_id}.pdf")


@app.get("/c/{order_id}", response_class=HTMLResponse)
def cupom_publico(order_id: str, request: Request):
    for pedido in PEDIDOS:
        if pedido["orderId"] == order_id:
            link = link_cupom(request, order_id)
            return HTMLResponse(pagina_cupom(pedido, link))
    return HTMLResponse(
        """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cupom não encontrado</title>
<style>body{font-family:Verdana,sans-serif;background:#FFFBFC;color:#7C4A3A;padding:32px;text-align:center}</style>
</head><body>
<h1>Esse cupom não existe</h1>
<p>O endereço ORD-XXXXXX era só um exemplo. Finalize uma venda no caixa para gerar o link de verdade, com um código como ORD-A1B2C3.</p>
</body></html>""",
        status_code=404,
    )


@app.get("/cardapio/pdf")
def cardapio_pdf():
    caminho = gerar_pdf_cardapio()
    return FileResponse(caminho, media_type="application/pdf", filename="Cardapio-Caminho-dos-Doces.pdf")


@app.get("/cardapio", response_class=HTMLResponse)
def cardapio_publico():
    return HTMLResponse(pagina_cardapio())


@app.get("/api/cardapio")
def listar_cardapio():
    return CARDAPIO


@app.put("/api/cardapio")
def salvar_cardapio(payload: CardapioSalvo):
    return gravar_cardapio(payload.itens)


@app.post("/api/cardapio/enviar")
def enviar_cardapio(payload: EnvioCardapio):
    if not payload.telefone.strip():
        raise HTTPException(status_code=400, detail="Informe o telefone para enviar o cardápio.")
    pdf = gerar_pdf_cardapio()
    aba = garantir_whatsapp("https://web.whatsapp.com/")
    enviar_pdf_no_whatsapp(aba, payload.telefone, legenda_cardapio(), pdf)
    return {"enviado": True}


@app.post("/api/whatsapp/abrir")
def abrir_whatsapp(payload: WhatsAppAbrir):
    return abrir_whatsapp_no_computador(payload.telefone, payload.texto, payload.pedido)


@app.post("/api/loja/abrir")
def abrir_loja(payload: LojaAbrir):
    return abrir_painel_loja(payload.canal.strip().lower())


def git_na_loja(*args: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", RAIZ, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def tem_repositorio() -> bool:
    return bool(shutil.which("git")) and os.path.isdir(os.path.join(RAIZ, ".git"))


def consultar_atualizacao() -> dict:
    if not tem_repositorio():
        return {"tem": False, "mensagens": []}
    ramo = git_na_loja("rev-parse", "--abbrev-ref", "@{upstream}")
    if ramo.returncode != 0 or not ramo.stdout.strip():
        return {"tem": False, "mensagens": []}
    busca = git_na_loja("fetch", "--quiet", timeout=25)
    if busca.returncode != 0:
        return {"tem": False, "mensagens": []}
    local = git_na_loja("rev-parse", "HEAD").stdout.strip()
    novo = git_na_loja("rev-parse", "@{upstream}").stdout.strip()
    if not local or not novo or local == novo:
        return {"tem": False, "mensagens": []}
    ancestra = git_na_loja("merge-base", "--is-ancestor", "HEAD", "@{upstream}")
    if ancestra.returncode != 0:
        return {"tem": False, "mensagens": []}
    registro = git_na_loja("log", "--format=%s", f"{local}..{novo}")
    frases = [linha.strip()[:140] for linha in registro.stdout.splitlines() if linha.strip()][:6]
    return {"tem": True, "mensagens": frases}


def _reiniciar_painel() -> None:
    time.sleep(0.5)
    python = sys.executable
    script = os.path.join(RAIZ, "main.py")
    if os.name == "nt":
        subprocess.Popen(
            ["cmd", "/c", f'timeout /t 2 /nobreak >nul & "{python}" "{script}"'],
            cwd=RAIZ,
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            ["/bin/bash", "-c", 'sleep 0.8; exec "$1" "$2"', "bash", python, script],
            cwd=RAIZ,
            start_new_session=True,
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    os.kill(os.getpid(), signal.SIGTERM)


@app.get("/api/atualizacao")
def ver_atualizacao():
    return consultar_atualizacao()


@app.post("/api/atualizacao")
def aplicar_atualizacao():
    info = consultar_atualizacao()
    if not info["tem"]:
        return {"ok": True, "reiniciar": False, "mensagem": "O PDV já está atualizado."}
    nomes = git_na_loja("diff", "--name-only", "HEAD", "@{upstream}")
    if any(linha.startswith("dados/") or linha.startswith("dados\\") for linha in nomes.stdout.splitlines()):
        raise HTTPException(status_code=400, detail="Essa atualização mexeria nos dados da loja. Não foi aplicada.")
    antes = git_na_loja("rev-parse", "HEAD").stdout.strip()
    puxar = git_na_loja("pull", "--ff-only", timeout=60)
    if puxar.returncode != 0:
        raise HTTPException(status_code=400, detail="Não deu para atualizar agora. Tente de novo daqui a pouco.")
    depois = git_na_loja("rev-parse", "HEAD").stdout.strip()
    if not depois or antes == depois:
        return {"ok": True, "reiniciar": False, "mensagem": "O PDV já está atualizado."}
    threading.Thread(target=_reiniciar_painel, daemon=True).start()
    return {"ok": True, "reiniciar": True, "mensagem": "Atualizado. O PDV vai abrir de novo sozinho."}


@app.get("/api/clientes")
def listar_clientes():
    return sorted(CLIENTES, key=lambda cliente: cliente.get("nome", "").lower())


@app.put("/api/clientes/{cliente_id}")
def organizar_cliente(cliente_id: str, payload: ClienteAgenda):
    if not payload.telefone.strip():
        raise HTTPException(status_code=400, detail="Informe o telefone.")
    nome = nome_e_sobrenome(payload.nome)
    cpf = cpf_formatado(payload.cpf)
    for cliente in CLIENTES:
        if cliente["id"] != cliente_id:
            continue
        cliente["nome"] = nome
        cliente["telefone"] = telefone_exibicao(payload.telefone)
        cliente["cpf"] = cpf
        cliente["endereco"] = payload.endereco.strip()
        cliente["observacoes"] = payload.observacoes.strip()
        cliente["organizado"] = True
        cliente["atualizadoEm"] = agora_texto()
        salvar()
        return cliente
    raise HTTPException(status_code=404, detail="Essa cliente não está na agenda.")


@app.post("/api/whatsapp/contatos")
def salvar_contatos_whatsapp():
    return importar_contatos_whatsapp()


class CancelamentoVenda(BaseModel):
    motivo: str


class AlterarPagamento(BaseModel):
    pagamento: str
    parcelas: int = 1
    valorPrimeiraParte: float = 0.0


def registrar_resultado(order_id: str, nome: str, resultado: float, agora: str) -> None:
    LIVRO_CAIXA[:] = [
        lancamento for lancamento in LIVRO_CAIXA
        if not (lancamento.get("orderId") == order_id and lancamento.get("tipo") == "RESULTADO")
    ]
    if abs(resultado) < 0.005:
        return
    categoria = "LUCRO" if resultado > 0 else "PREJUIZO"
    LIVRO_CAIXA.append({
        "id": f"CX-{uuid.uuid4().hex[:6].upper()}",
        "orderId": order_id,
        "descricao": f"{categoria} {order_id} — {nome}",
        "tipo": "RESULTADO",
        "categoria": categoria,
        "valor": round(abs(resultado), 2),
        "criadoEm": agora,
    })


@app.put("/api/pedidos/{order_id}/pagamento")
def alterar_pagamento(order_id: str, payload: AlterarPagamento, request: Request):
    pedido = next((item for item in PEDIDOS if item["orderId"] == order_id), None)
    if not pedido:
        raise HTTPException(status_code=404, detail="Essa venda não está no caixa.")
    if "valorCobrado" in pedido:
        base = float(pedido["valorCobrado"])
    else:
        base = round(float(pedido.get("subtotal") or 0) + float(pedido.get("taxaEntrega") or 0), 2)
    conta = fechar_pagamento(payload, base)
    antigo = round(
        sum(
            lancamento["valor"]
            for lancamento in LIVRO_CAIXA
            if lancamento.get("orderId") == order_id and lancamento.get("tipo") == "ENTRADA"
        ),
        2,
    )
    tipo_lancamento = "SINAL" if conta["restante"] > 0 else "VENDA"
    entradas = [
        lancamento for lancamento in LIVRO_CAIXA
        if lancamento.get("orderId") == order_id and lancamento.get("tipo") == "ENTRADA"
    ]
    if len(entradas) == 1:
        entradas[0]["valor"] = conta["sinal"]
        entradas[0]["categoria"] = tipo_lancamento
        entradas[0]["descricao"] = f"{tipo_lancamento} {order_id} — {pedido['nome']}"
    else:
        delta = round(conta["sinal"] - antigo, 2)
        if delta:
            LIVRO_CAIXA.append({
                "id": f"CX-{uuid.uuid4().hex[:6].upper()}",
                "orderId": order_id,
                "descricao": f"Ajuste {order_id} — {pedido['nome']}",
                "tipo": "ENTRADA" if delta > 0 else "SAIDA",
                "categoria": "AJUSTE",
                "valor": abs(delta),
                "criadoEm": agora_texto(),
            })
    CAIXA["saldo"] = round(CAIXA["saldo"] - antigo + conta["sinal"], 2)
    CAIXA["gavetaEm"] = ""
    pedido.update({
        "metodo": payload.pagamento,
        "total": conta["total"],
        "sinal": conta["sinal"],
        "restante": conta["restante"],
        "pagamento": conta["descricao"],
        "partes": conta["partes"],
        "statusPagamento": conta["statusPagamento"],
        "lembrete": conta["lembrete"],
        "juros": conta["juros"],
    })
    salvar()
    return {"pedido": pedido_publico(request, pedido), "caixa": CAIXA}


def hash_senha(senha: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt), 120_000).hex()


def garantir_senha_admin() -> bool:
    if ADMIN.get("senha") and ADMIN.get("salt"):
        return False
    salt = secrets.token_hex(16)
    ADMIN["salt"] = salt
    ADMIN["senha"] = hash_senha("000000", salt)
    ADMIN.setdefault("empresaSaldo", 0.0)
    ADMIN.setdefault("empresaLimite", 0.0)
    ADMIN.setdefault("empresaCartaoUsado", 0.0)
    ADMIN.setdefault("nubankSaldo", 0.0)
    ADMIN.setdefault("metaMes", 0.0)
    return True


def senha_confere(senha: str) -> bool:
    salt = ADMIN.get("salt") or ""
    guardada = ADMIN.get("senha") or ""
    if not salt or not guardada:
        return False
    return secrets.compare_digest(hash_senha(senha, salt), guardada)


def exigir_admin(request: Request) -> None:
    token = request.headers.get("x-admin", "")
    validade = TOKENS_ADMIN.get(token)
    if not validade or validade < time.time():
        TOKENS_ADMIN.pop(token, None)
        raise HTTPException(status_code=401, detail="Entre de novo na área administrativa.")
    TOKENS_ADMIN[token] = time.time() + 12 * 3600


def _percentual(valor, padrao: float) -> float:
    if valor is None:
        valor = padrao
    numero = float(valor or 0)
    if numero < 0:
        numero = 0
    if numero > 80:
        numero = 80
    return round(numero, 2)


def _reais(valor, padrao: float) -> float:
    if valor is None:
        valor = padrao
    return round(max(float(valor or 0), 0), 2)


def conta_ifood(dados: dict | None = None) -> dict:
    dados = dados or {}
    bruto = round(max(float(dados.get("ifoodSaldo") or 0), 0), 2)
    plano = dados.get("ifoodPlano") or "BASICO"
    if plano not in ("BASICO", "ENTREGA"):
        plano = "BASICO"
    pagamento = dados.get("ifoodPagamento") or "APP"
    if pagamento not in ("APP", "ENTREGA"):
        pagamento = "APP"
    antecipacao = dados.get("ifoodAntecipacao") or "NENHUMA"
    if antecipacao not in ("NENHUMA", "SEMANAL", "SEMANAL_DIGITAL", "SOB_DEMANDA"):
        antecipacao = "NENHUMA"
    comissao_padrao = 23.0 if plano == "ENTREGA" else 12.0
    mensalidade_padrao = 150.0 if plano == "ENTREGA" else 110.0
    comissao = _percentual(dados.get("ifoodComissao"), comissao_padrao)
    taxa_pagamento = _percentual(dados.get("ifoodTaxaPagamento"), 3.2 if pagamento == "APP" else 0)
    taxa_antecipacao = _percentual(dados.get("ifoodTaxaAntecipacao"), 0)
    mensalidade = _reais(dados.get("ifoodMensalidade"), mensalidade_padrao)
    isencao = _reais(dados.get("ifoodIsencao"), 1800)
    pag_aplicada = taxa_pagamento if pagamento == "APP" else 0.0
    ant_aplicada = taxa_antecipacao if pagamento == "APP" else 0.0
    total = round(comissao + pag_aplicada + ant_aplicada, 2)
    estoura = total >= 100
    juros = round(bruto * total / 100, 2) if bruto > 0 and not estoura else 0.0

    def parte(percentual: float) -> float:
        if estoura or total <= 0 or bruto <= 0:
            return 0.0
        return round(bruto * percentual / 100, 2)

    comissao_rs = parte(comissao)
    pag_rs = parte(pag_aplicada)
    ant_rs = parte(ant_aplicada)
    comissao_rs = round(comissao_rs + (juros - (comissao_rs + pag_rs + ant_rs)), 2)
    isenta = bruto <= isencao
    mensalidade_cobrada = 0.0 if isenta else mensalidade
    liquido = round(bruto - juros - mensalidade_cobrada, 2)
    return {
        "saldo": bruto,
        "plano": plano,
        "pagamento": pagamento,
        "antecipacao": antecipacao,
        "comissao": comissao,
        "taxaPagamento": taxa_pagamento,
        "taxaAntecipacao": taxa_antecipacao,
        "pagAplicada": pag_aplicada,
        "antAplicada": ant_aplicada,
        "taxa": total,
        "bruto": bruto,
        "juros": juros,
        "comissaoRs": comissao_rs,
        "pagamentoRs": pag_rs,
        "antecipacaoRs": ant_rs,
        "mensalidade": mensalidade,
        "isencao": isencao,
        "isenta": isenta,
        "mensalidadeCobrada": mensalidade_cobrada,
        "liquido": liquido,
        "estoura": estoura,
    }


def conta_noventa(dados: dict | None = None) -> dict:
    dados = dados or {}
    bruto = round(max(float(dados.get("noventaSaldo") or 0), 0), 2)
    plano = dados.get("noventaPlano") or "PARCEIRA"
    if plano not in ("PARCEIRA", "PROPRIA"):
        plano = "PARCEIRA"
    pagamento = dados.get("noventaPagamento") or "APP"
    if pagamento not in ("APP", "ENTREGA"):
        pagamento = "APP"
    repasse = dados.get("noventaRepasse") or "NENHUMA"
    if repasse not in ("NENHUMA", "SEMANAL", "DIARIO"):
        repasse = "NENHUMA"
    comissao_padrao = 10.9 if plano == "PROPRIA" else 8.9
    comissao = _percentual(dados.get("noventaComissao"), comissao_padrao)
    taxa_pagamento = _percentual(dados.get("noventaTaxaPagamento"), 3.2 if pagamento == "APP" else 0)
    logistica = _percentual(dados.get("noventaLogistica"), 0)
    taxa_saque = _percentual(dados.get("noventaTaxaSaque"), 0)
    mensalidade = _reais(dados.get("noventaMensalidade"), 0)
    pag_aplicada = taxa_pagamento if pagamento == "APP" else 0.0
    log_aplicada = logistica if plano == "PARCEIRA" else 0.0
    total = round(comissao + pag_aplicada + log_aplicada + taxa_saque, 2)
    estoura = total >= 100
    juros = round(bruto * total / 100, 2) if bruto > 0 and not estoura else 0.0

    def parte(percentual: float) -> float:
        if estoura or total <= 0 or bruto <= 0:
            return 0.0
        return round(bruto * percentual / 100, 2)

    comissao_rs = parte(comissao)
    pag_rs = parte(pag_aplicada)
    log_rs = parte(log_aplicada)
    saque_rs = parte(taxa_saque)
    comissao_rs = round(comissao_rs + (juros - (comissao_rs + pag_rs + log_rs + saque_rs)), 2)
    liquido = round(bruto - juros - mensalidade, 2)
    return {
        "saldo": bruto,
        "plano": plano,
        "pagamento": pagamento,
        "repasse": repasse,
        "comissao": comissao,
        "taxaPagamento": taxa_pagamento,
        "logistica": logistica,
        "taxaSaque": taxa_saque,
        "pagAplicada": pag_aplicada,
        "logAplicada": log_aplicada,
        "taxa": total,
        "bruto": bruto,
        "juros": juros,
        "comissaoRs": comissao_rs,
        "pagamentoRs": pag_rs,
        "logisticaRs": log_rs,
        "saqueRs": saque_rs,
        "mensalidade": mensalidade,
        "mensalidadeCobrada": mensalidade,
        "isenta": mensalidade <= 0,
        "liquido": liquido,
        "estoura": estoura,
    }


def admin_publico() -> dict:
    limite = float(ADMIN.get("empresaLimite") or 0)
    usado = float(ADMIN.get("empresaCartaoUsado") or 0)
    empresa = float(ADMIN.get("empresaSaldo") or 0)
    nubank = float(ADMIN.get("nubankSaldo") or 0)
    ifood_forma = ADMIN.get("ifoodForma") or "PIX"
    noventa_forma = ADMIN.get("noventaForma") or "PIX"
    ifood = conta_ifood(ADMIN)
    noventa = conta_noventa(ADMIN)
    return {
        "empresaSaldo": empresa,
        "empresaLimite": limite,
        "empresaCartaoUsado": usado,
        "empresaCartaoLivre": round(max(limite - usado, 0), 2),
        "nubankSaldo": nubank,
        "somaContas": round(empresa + nubank, 2),
        "metaMes": float(ADMIN.get("metaMes") or 0),
        "cartaoVencimento": int(ADMIN.get("cartaoVencimento") or 0),
        "ifoodSaldo": float(ADMIN.get("ifoodSaldo") or 0),
        "ifoodForma": ifood_forma,
        "ifoodTaxa": float(ADMIN.get("ifoodTaxa") or 0),
        "ifoodPlano": ifood["plano"],
        "ifoodPagamento": ifood["pagamento"],
        "ifoodComissao": ifood["comissao"],
        "ifoodTaxaPagamento": ifood["taxaPagamento"],
        "ifoodMensalidade": ifood["mensalidade"],
        "ifoodIsencao": ifood["isencao"],
        "ifoodAntecipacao": ifood["antecipacao"],
        "ifoodTaxaAntecipacao": ifood["taxaAntecipacao"],
        "noventaSaldo": float(ADMIN.get("noventaSaldo") or 0),
        "noventaForma": noventa_forma,
        "noventaTaxa": float(ADMIN.get("noventaTaxa") or 0),
        "noventaPlano": noventa["plano"],
        "noventaPagamento": noventa["pagamento"],
        "noventaComissao": noventa["comissao"],
        "noventaTaxaPagamento": noventa["taxaPagamento"],
        "noventaLogistica": noventa["logistica"],
        "noventaMensalidade": noventa["mensalidade"],
        "noventaRepasse": noventa["repasse"],
        "noventaTaxaSaque": noventa["taxaSaque"],
        "ifood": ifood,
        "noventa": noventa,
        "prolabore": prolabore_publico(),
        "casa": casa_publica(),
    }


def do_mes(texto: str) -> bool:
    agora = datetime.now()
    try:
        dia = datetime.strptime((texto or "")[:10], "%d/%m/%Y")
    except ValueError:
        return False
    return dia.month == agora.month and dia.year == agora.year


def regime_motoboy(valor: str) -> str:
    texto = (valor or "").strip().upper()
    if texto in ("ANEXO_IV", "ANEXO4", "IV"):
        return "ANEXO_IV"
    if texto in ("LUCRO", "PRESUMIDO", "REAL"):
        return "LUCRO"
    return "SIMPLES"


def inss_colaborador(salario: float) -> float:
    base = min(max(salario, 0.0), 8475.55)
    faixas = ((1621.00, 0.075), (2902.84, 0.09), (4354.27, 0.12), (8475.55, 0.14))
    anterior = 0.0
    total = 0.0
    for teto, aliquota in faixas:
        if base <= anterior:
            break
        total += (min(base, teto) - anterior) * aliquota
        anterior = teto
    return round(total, 2)


def ir_tabela(base: float) -> float:
    tabela = (
        (2428.80, 0.0, 0.0),
        (2826.65, 0.075, 182.16),
        (3751.05, 0.15, 394.16),
        (4664.68, 0.225, 675.49),
        (float("inf"), 0.275, 908.73),
    )
    for teto, aliquota, deducao in tabela:
        if base <= teto:
            return round(max(base * aliquota - deducao, 0), 2)
    return 0.0


def irrf_colaborador(bruto: float, inss: float, dependentes: int) -> float:
    dependentes = max(int(dependentes or 0), 0)
    base_legal = max(bruto - inss - dependentes * 189.59, 0)
    base_simples = max(bruto - 607.20, 0)
    imposto = min(ir_tabela(base_legal), ir_tabela(base_simples))
    if bruto <= 5000:
        reducao = 312.89
    elif bruto <= 7350:
        reducao = max(978.62 - (0.133145 * bruto), 0)
    else:
        reducao = 0.0
    return round(max(imposto - reducao, 0), 2)


def taxa_folha(valor, padrao: float) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    if numero != numero:
        return padrao
    return min(max(numero, 0.0), 100.0)


def calcular_motoboy(
    salario: float,
    regime: str,
    rat: float,
    sistema_s: float,
    vale_transporte: float,
    vale_alimentacao: float,
    dependentes: int,
    comparar: bool = True,
    pct_vt: float = 6,
    pct_va: float = 20,
    teto_descontos: float = 70,
    pct_fgts: float = 8,
    pct_ferias: float = 11.11,
    pct_decimo: float = 8.33,
    pct_multa: float = 4,
    pct_patronal: float = 20,
    pct_educacao: float = 2.5,
) -> dict:
    salario = round(max(float(salario or 0), 0), 2)
    vale_transporte = round(max(float(vale_transporte or 0), 0), 2)
    vale_alimentacao = round(max(float(vale_alimentacao or 0), 0), 2)
    regime = regime_motoboy(regime)
    pct_vt = taxa_folha(pct_vt, 6)
    pct_va = taxa_folha(pct_va, 20)
    teto_descontos = taxa_folha(teto_descontos, 70)
    pct_fgts = taxa_folha(pct_fgts, 8)
    pct_ferias = taxa_folha(pct_ferias, 11.11)
    pct_decimo = taxa_folha(pct_decimo, 8.33)
    pct_multa = taxa_folha(pct_multa, 4)
    pct_patronal = taxa_folha(pct_patronal, 20)
    pct_educacao = taxa_folha(pct_educacao, 2.5)
    rat = taxa_folha(rat, 2)
    sistema_s = taxa_folha(sistema_s, 5.8)
    inss = inss_colaborador(salario)
    irrf = irrf_colaborador(salario, inss, dependentes)
    desconto_vt_cheio = round(min(vale_transporte, salario * (pct_vt / 100.0)), 2)
    desconto_va_cheio = round(min(vale_alimentacao, vale_alimentacao * (pct_va / 100.0)), 2)
    teto_valor = round(salario * (teto_descontos / 100.0), 2)
    folga = round(max(teto_valor - inss - irrf, 0), 2)
    desconto_vt = round(min(desconto_vt_cheio, folga), 2)
    desconto_va = round(min(desconto_va_cheio, max(folga - desconto_vt, 0)), 2)
    limite = desconto_vt + desconto_va + 0.001 < desconto_vt_cheio + desconto_va_cheio
    legal_acima = inss + irrf > teto_valor + 0.001
    liquido = round(max(salario - inss - irrf - desconto_vt - desconto_va, 0), 2)
    piso = round(salario * ((100.0 - teto_descontos) / 100.0), 2)
    fgts = round(salario * (pct_fgts / 100.0), 2)
    ferias = round(salario * (pct_ferias / 100.0), 2)
    decimo = round(salario * (pct_decimo / 100.0), 2)
    multa = round(salario * (pct_multa / 100.0), 2)
    guardar = round(ferias + decimo + multa, 2)
    folha_cheia = regime != "SIMPLES"
    inss_patronal = round(salario * (pct_patronal / 100.0), 2) if folha_cheia else 0.0
    rat_valor = round(salario * (rat / 100.0), 2) if folha_cheia else 0.0
    educacao = round(salario * (pct_educacao / 100.0), 2) if folha_cheia else 0.0
    sistema_valor = round(salario * (sistema_s / 100.0), 2) if folha_cheia else 0.0
    custo_vt = round(max(vale_transporte - desconto_vt, 0), 2)
    custo_va = round(max(vale_alimentacao - desconto_va, 0), 2)
    sai = round(
        salario + fgts + inss_patronal + rat_valor + educacao + sistema_valor + custo_vt + custo_va,
        2,
    )
    cheio = round(sai + guardar, 2)
    vezes = round(cheio / salario, 2) if salario else 0.0
    conta = {
        "salario": salario,
        "regime": regime,
        "rat": rat,
        "sistemaS": sistema_s,
        "dependentes": max(int(dependentes or 0), 0),
        "inss": inss,
        "irrf": irrf,
        "descontoVale": desconto_vt,
        "descontoAlimentacao": desconto_va,
        "liquido": liquido,
        "pisoLiquido": piso,
        "limiteDescontos": limite,
        "legalAcimaDoTeto": legal_acima,
        "fgts": fgts,
        "ferias": ferias,
        "decimo": decimo,
        "multa": multa,
        "guardarMes": guardar,
        "guardarAno": round(guardar * 12, 2),
        "inssPatronal": inss_patronal,
        "ratValor": rat_valor,
        "educacao": educacao,
        "sistemaValor": sistema_valor,
        "valeTransporte": vale_transporte,
        "custoVale": custo_vt,
        "valeAlimentacao": vale_alimentacao,
        "custoAlimentacao": custo_va,
        "saiCaixa": sai,
        "custoCheio": cheio,
        "custoAno": round(cheio * 12, 2),
        "vezes": vezes,
        "folhaCheia": folha_cheia,
        "pctValeTransporte": pct_vt,
        "pctValeAlimentacao": pct_va,
        "tetoDescontos": teto_descontos,
        "pctFgts": pct_fgts,
        "pctFerias": pct_ferias,
        "pctDecimo": pct_decimo,
        "pctMulta": pct_multa,
        "pctPatronal": pct_patronal,
        "pctEducacao": pct_educacao,
    }
    if comparar:
        conta["comparar"] = {
            nome: calcular_motoboy(
                salario,
                nome,
                rat,
                sistema_s,
                vale_transporte,
                vale_alimentacao,
                dependentes,
                False,
                pct_vt,
                pct_va,
                teto_descontos,
                pct_fgts,
                pct_ferias,
                pct_decimo,
                pct_multa,
                pct_patronal,
                pct_educacao,
            )
            for nome in ("SIMPLES", "ANEXO_IV", "LUCRO")
        }
    return conta


def prolabore_publico() -> dict:
    atual = ADMIN.get("prolabore") or {}
    guardado = bool(atual)

    def num(chave: str) -> float:
        try:
            return round(max(float(atual.get(chave) or 0), 0), 2)
        except (TypeError, ValueError):
            return 0.0

    calendario = str(atual.get("calendario") or "TRIMESTRAL").strip().upper()
    if calendario not in ("TRIMESTRAL", "SEMESTRAL", "ANUAL", "NENHUM"):
        calendario = "TRIMESTRAL"
    try:
        dia = int(atual.get("dia") or 5)
    except (TypeError, ValueError):
        dia = 5
    try:
        meses_pj = int(atual.get("mesesReservaPj") or 3)
    except (TypeError, ValueError):
        meses_pj = 3
    try:
        meses_pf = int(atual.get("mesesReservaPf") or 6)
    except (TypeError, ValueError):
        meses_pf = 6
    try:
        dependentes = int(atual.get("dependentes") or 0)
    except (TypeError, ValueError):
        dependentes = 0
    return {
        "moradia": num("moradia"),
        "saude": num("saude"),
        "educacao": num("educacao"),
        "alimentacao": num("alimentacao"),
        "outrasPessoais": num("outrasPessoais"),
        "metaPessoal": num("metaPessoal"),
        "mercado": num("mercado"),
        "aluguel": num("aluguel"),
        "contasLoja": num("contasLoja"),
        "contador": num("contador"),
        "outrasLoja": num("outrasLoja"),
        "prolaboreFixo": num("prolaboreFixo"),
        "reservaPfGuardada": num("reservaPfGuardada"),
        "dependentes": max(dependentes, 0),
        "dia": min(max(dia, 1), 28),
        "calendario": calendario,
        "pctDistribuir": taxa_folha(atual.get("pctDistribuir", 50), 50),
        "pctInss": taxa_folha(atual.get("pctInss", 11), 11),
        "mesesReservaPj": min(max(meses_pj, 3), 6),
        "mesesReservaPf": min(max(meses_pf, 6), 12),
        "regime": regime_motoboy(str(atual.get("regime") or "SIMPLES")),
        "aplicarRegime": guardado,
    }


def calcular_prolabore(
    custo_vida: float,
    mercado: float,
    prolabore_fixo: float,
    liquido_mes: float,
    fixos: float,
    saldo_loja: float,
    reserva_pf: float,
    reserva_contratado: float,
    mensalidades: float,
    regime: str,
    rat: float,
    sistema_s: float,
    dependentes: int,
    pct_inss: float = 11,
    teto_descontos: float = 70,
    pct_patronal: float = 20,
    pct_educacao: float = 2.5,
    meses_pj: int = 3,
    meses_pf: int = 6,
    pct_distribuir: float = 50,
    calendario: str = "TRIMESTRAL",
    dia: int = 5,
) -> dict:
    custo_vida = round(max(float(custo_vida or 0), 0), 2)
    mercado = round(max(float(mercado or 0), 0), 2)
    prolabore_fixo = round(max(float(prolabore_fixo or 0), 0), 2)
    liquido_mes = round(float(liquido_mes or 0), 2)
    fixos = round(max(float(fixos or 0), 0), 2)
    saldo_loja = round(max(float(saldo_loja or 0), 0), 2)
    reserva_contratado = round(max(float(reserva_contratado or 0), 0), 2)
    mensalidades = round(max(float(mensalidades or 0), 0), 2)
    reserva_pf = round(max(float(reserva_pf or 0), 0), 2)
    regime = regime_motoboy(regime)
    pct_inss = taxa_folha(pct_inss, 11)
    teto_descontos = taxa_folha(teto_descontos, 70)
    pct_patronal = taxa_folha(pct_patronal, 20)
    pct_educacao = taxa_folha(pct_educacao, 2.5)
    rat = taxa_folha(rat, 2)
    sistema_s = taxa_folha(sistema_s, 5.8)
    pct_distribuir = taxa_folha(pct_distribuir, 50)
    meses_pj = min(max(int(meses_pj or 3), 3), 6)
    meses_pf = min(max(int(meses_pf or 6), 6), 12)
    folha_cheia = regime != "SIMPLES"
    aliq = (pct_patronal + rat + pct_educacao + sistema_s) / 100.0 if folha_cheia else 0.0
    disponivel = round(liquido_mes - fixos, 2)
    bruto_max = round(max(disponivel, 0) / (1 + aliq), 2)
    if mercado > 0 and custo_vida > mercado:
        base = mercado
    elif custo_vida > 0 and mercado > 0:
        base = min(custo_vida, mercado)
    else:
        base = custo_vida or mercado
    sugerido = round(min(base, bruto_max), 2) if base > 0 else 0.0
    escolhido = prolabore_fixo if prolabore_fixo > 0 else sugerido
    if escolhido <= 0:
        inss = 0.0
    else:
        base_inss = min(max(escolhido, 1621.0), 8475.55)
        inss = round(base_inss * (pct_inss / 100.0), 2)
    irrf = irrf_colaborador(escolhido, inss, dependentes) if escolhido else 0.0
    teto_valor = round(escolhido * (teto_descontos / 100.0), 2)
    liquido_pf = round(max(escolhido - inss - irrf, 0), 2)
    piso = round(escolhido * ((100.0 - teto_descontos) / 100.0), 2)
    patronal = round(escolhido * (pct_patronal / 100.0), 2) if folha_cheia else 0.0
    rat_valor = round(escolhido * (rat / 100.0), 2) if folha_cheia else 0.0
    educacao = round(escolhido * (pct_educacao / 100.0), 2) if folha_cheia else 0.0
    sistema_valor = round(escolhido * (sistema_s / 100.0), 2) if folha_cheia else 0.0
    custo_loja = round(escolhido + patronal + rat_valor + educacao + sistema_valor, 2)
    estoura = custo_loja > max(disponivel, 0) + 0.001
    sobra = round(liquido_mes - fixos - custo_loja, 2)
    fixos_mes = round(fixos + custo_loja + reserva_contratado + mensalidades, 2)
    reserva_pj = round(fixos_mes * meses_pj, 2)
    reserva_pf_meta = round(custo_vida * meses_pf, 2)
    falta_pj = round(max(reserva_pj - saldo_loja, 0), 2)
    falta_pf = round(max(reserva_pf_meta - reserva_pf, 0), 2)
    gap_vida = round(max(custo_vida - liquido_pf, 0), 2)
    mes = datetime.now().month
    mapas = {"TRIMESTRAL": (3, 6, 9, 12), "SEMESTRAL": (6, 12), "ANUAL": (12,), "NENHUM": ()}
    neste = mes in mapas.get(calendario, ())
    pode = sobra > 0 and falta_pj <= 0 and neste
    distribuir = round(sobra * (pct_distribuir / 100.0), 2) if pode else 0.0
    fica = round(sobra - distribuir, 2) if sobra > 0 else 0.0
    return {
        "custoVida": custo_vida,
        "mercado": mercado,
        "sugerido": sugerido,
        "prolabore": escolhido,
        "inss": inss,
        "irrf": irrf,
        "liquidoPf": liquido_pf,
        "pisoLiquido": piso,
        "patronal": patronal,
        "ratValor": rat_valor,
        "educacao": educacao,
        "sistemaValor": sistema_valor,
        "custoLoja": custo_loja,
        "estoura": estoura,
        "sobra": sobra,
        "reservaPj": reserva_pj,
        "reservaPf": reserva_pf_meta,
        "faltaPj": falta_pj,
        "faltaPf": falta_pf,
        "gapVida": gap_vida,
        "distribuir": distribuir,
        "ficaLoja": fica,
        "folhaCheia": folha_cheia,
        "regime": regime,
        "dia": min(max(int(dia or 5), 1), 28),
        "calendario": calendario,
        "brutoMax": bruto_max,
    }


CONTAS_CASA = (
    ("aluguel", True), ("iptu", True), ("luz", True), ("agua", True), ("gas", True),
    ("internet", True), ("telefone", True), ("mercado", False), ("saude", False),
    ("educacao", False), ("transporte", False), ("lazer", False), ("assinaturas", False),
    ("outras", False),
)
NOMES_CONTAS = {
    "aluguel": "Aluguel",
    "iptu": "IPTU",
    "luz": "Energia elétrica",
    "agua": "Água",
    "gas": "Gás",
    "internet": "Internet",
    "telefone": "Telefone",
    "mercado": "Mercado da casa",
    "saude": "Saúde",
    "educacao": "Educação",
    "transporte": "Transporte",
    "lazer": "Lazer",
    "assinaturas": "Assinaturas",
    "outras": "Outras contas da casa",
}
FORMAS_CASA = ("PIX", "DINHEIRO", "DEBITO", "CREDITO", "BOLETO")


def percentuais_casa(dados: dict) -> dict:
    area_total = max(float(dados.get("areaTotal") or 0), 0)
    area_loja = max(float(dados.get("areaLoja") or 0), 0)
    if area_total > 0 and area_loja > 0:
        pct_area = round(min(area_loja, area_total) / area_total * 100, 2)
    else:
        pct_area = taxa_folha(dados.get("pctAluguel", 30), 30)
    kwh_conta = max(float(dados.get("kwhConta") or 0), 0)
    kwh_loja = max(float(dados.get("kwhLoja") or 0), 0)
    if kwh_conta > 0 and kwh_loja > 0:
        pct_luz = round(min(kwh_loja, kwh_conta) / kwh_conta * 100, 2)
    else:
        pct_luz = taxa_folha(dados.get("pctLuz", 70), 70)
    gas_modo = "ENCANADO" if str(dados.get("gasModo") or "").upper() == "ENCANADO" else "BOTIJAO"
    pct_gas = 100.0 if gas_modo == "BOTIJAO" else taxa_folha(dados.get("pctGas", 65), 65)
    pct_telefone = 100.0 if dados.get("telefoneExclusivo") else taxa_folha(dados.get("pctTelefone", 50), 50)
    return {
        "aluguel": pct_area,
        "iptu": pct_area,
        "luz": pct_luz,
        "agua": taxa_folha(dados.get("pctAgua", 55), 55),
        "gas": pct_gas,
        "internet": taxa_folha(dados.get("pctInternet", 50), 50),
        "telefone": pct_telefone,
        "pctArea": pct_area,
        "pctLuz": pct_luz,
        "gasModo": gas_modo,
    }


def calcular_casa(dados: dict) -> dict:
    pct = percentuais_casa(dados)
    contas = dados.get("contas") or {}
    itens = []
    for chave, compartilhada in CONTAS_CASA:
        atual = contas.get(chave) or {}
        bruto = round(max(float(atual.get("valor") or 0), 0), 2)
        parte = pct[chave] if compartilhada else 0.0
        loja = round(bruto * parte / 100.0, 2)
        pf = round(bruto - loja, 2)
        pagador = "LOJA" if str(atual.get("pagador") or "CASA").upper() == "LOJA" else "CASA"
        itens.append({
            "id": chave,
            "compartilhada": compartilhada,
            "bruto": bruto,
            "parte": parte,
            "loja": loja,
            "pf": pf,
            "pagador": pagador,
        })
    loja_total = round(sum(item["loja"] for item in itens), 2)
    casa_total = round(sum(item["pf"] for item in itens), 2)
    loja_deve = round(sum(item["loja"] for item in itens if item["pagador"] == "CASA"), 2)
    casa_deve = round(sum(item["pf"] for item in itens if item["pagador"] == "LOJA"), 2)
    aluguel_loja = round(sum(item["loja"] for item in itens if item["id"] in ("aluguel", "iptu")), 2)
    contas_loja = round(sum(item["loja"] for item in itens if item["id"] in ("luz", "agua", "gas", "internet", "telefone")), 2)
    sentido = "LOJA_PARA_CASA" if loja_deve >= casa_deve else "CASA_PARA_LOJA"
    return {
        "itens": itens,
        "lojaTotal": loja_total,
        "casaTotal": casa_total,
        "aluguelLoja": aluguel_loja,
        "contasLoja": contas_loja,
        "transferencia": round(abs(loja_deve - casa_deve), 2),
        "sentido": sentido,
        "pct": pct,
    }


def casa_publica() -> dict:
    atual = ADMIN.get("casa") or {}
    contas = atual.get("contas") or {}
    saida_contas = {}
    for chave, _compartilhada in CONTAS_CASA:
        item = contas.get(chave) or {}
        try:
            valor = round(max(float(item.get("valor") or 0), 0), 2)
        except (TypeError, ValueError):
            valor = 0.0
        try:
            dia = int(item.get("dia") or 10)
        except (TypeError, ValueError):
            dia = 10
        forma = str(item.get("forma") or "PIX").upper()
        if forma not in FORMAS_CASA:
            forma = "PIX"
        pagador = "LOJA" if str(item.get("pagador") or "CASA").upper() == "LOJA" else "CASA"
        saida_contas[chave] = {
            "valor": valor,
            "dia": min(max(dia, 1), 28),
            "forma": forma,
            "cartao": str(item.get("cartao") or ""),
            "pagador": pagador,
            "nome": str(item.get("nome") or "").strip()[:80],
        }
    cartoes = []
    for cartao in atual.get("cartoes") or []:
        if not isinstance(cartao, dict):
            continue
        final = "".join(ch for ch in str(cartao.get("final") or "") if ch.isdigit())[-4:]
        nome = str(cartao.get("nome") or "").strip()
        if len(final) != 4 or not nome:
            continue
        try:
            limite = round(max(float(cartao.get("limite") or 0), 0), 2)
        except (TypeError, ValueError):
            limite = 0.0
        cartoes.append({
            "id": str(cartao.get("id") or f"CARD-{uuid.uuid4().hex[:6].upper()}"),
            "nome": nome[:40],
            "final": final,
            "limite": limite,
            "fecha": min(max(int(cartao.get("fecha") or 1), 1), 28),
            "vence": min(max(int(cartao.get("vence") or 10), 1), 28),
            "dono": "LOJA" if str(cartao.get("dono") or "CASA").upper() == "LOJA" else "CASA",
        })

    def num(chave: str, padrao: float = 0) -> float:
        try:
            return round(max(float(atual.get(chave) if atual.get(chave) is not None else padrao), 0), 2)
        except (TypeError, ValueError):
            return padrao

    gas_modo = "ENCANADO" if str(atual.get("gasModo") or "").upper() == "ENCANADO" else "BOTIJAO"
    return {
        "areaTotal": num("areaTotal"),
        "areaLoja": num("areaLoja"),
        "pctAluguel": taxa_folha(atual.get("pctAluguel", 30), 30),
        "kwhConta": num("kwhConta"),
        "kwhLoja": num("kwhLoja"),
        "pctLuz": taxa_folha(atual.get("pctLuz", 70), 70),
        "pctAgua": taxa_folha(atual.get("pctAgua", 55), 55),
        "gasModo": gas_modo,
        "pctGas": taxa_folha(atual.get("pctGas", 65), 65),
        "pctInternet": taxa_folha(atual.get("pctInternet", 50), 50),
        "pctTelefone": taxa_folha(atual.get("pctTelefone", 50), 50),
        "telefoneExclusivo": bool(atual.get("telefoneExclusivo")),
        "receitas": num("receitas"),
        "saldoPessoal": num("saldoPessoal"),
        "cartoes": cartoes,
        "contas": saida_contas,
    }


def ler_imagem_aviso(conteudo: bytes) -> str:
    if not conteudo or not shutil.which("tesseract"):
        return ""
    sufixo = ".png"
    with tempfile.NamedTemporaryFile(suffix=sufixo, delete=True) as tmp:
        tmp.write(conteudo)
        tmp.flush()
        comando = ["tesseract", tmp.name, "stdout", "-l", "por+eng"]
        try:
            saida = subprocess.run(comando, capture_output=True, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        if saida.returncode != 0:
            try:
                saida = subprocess.run(["tesseract", tmp.name, "stdout"], capture_output=True, timeout=20, check=False)
            except (OSError, subprocess.TimeoutExpired):
                return ""
        return saida.stdout.decode("utf-8", errors="ignore").strip()


def resumo_periodo(so_mes: bool) -> dict:
    bruto = 0.0
    juros = 0.0
    motoboy = 0.0
    for pedido in PEDIDOS:
        if so_mes and not do_mes(pedido.get("criadoEm", "")):
            continue
        cobrado = float(pedido["valorCobrado"]) if "valorCobrado" in pedido else float(pedido.get("total") or 0)
        if "sinal" in pedido:
            entrou = float(pedido.get("sinal") or 0) + float(pedido.get("restante") or 0)
        else:
            entrou = cobrado
        bruto += entrou
        if entrou > cobrado:
            juros += entrou - cobrado
        if pedido.get("entrega") in ENTREGAS_DA_LOJA:
            motoboy += float(pedido.get("taxaEntrega") or 0)
    ifood = 0.0
    noventa = 0.0
    for taxa in TAXAS_PAGAS:
        if so_mes and not do_mes(taxa.get("criadoEm", "")):
            continue
        valor = float(taxa.get("valor") or 0)
        if taxa.get("canal") == "MOTOBOY":
            motoboy += valor
        elif taxa.get("canal") == "IFOOD":
            ifood += valor
        elif taxa.get("canal") == "NOVENTA":
            noventa += valor
    diarias = 0.0
    reserva = 0.0
    prolabore = 0.0
    ocupacao = 0.0
    for item in FOLHA:
        if so_mes and not do_mes(item.get("criadoEm", "")):
            continue
        if item.get("tipo") == "DIARIA":
            diarias += float(item.get("valor") or 0)
        elif item.get("tipo") == "RESERVA":
            reserva += float(item.get("custoCheio") or 0)
        elif item.get("tipo") == "PROLABORE":
            prolabore += float(item.get("custoLoja") or 0)
        elif item.get("tipo") == "OCUPACAO":
            ocupacao += float(item.get("custoLoja") or 0)
    mantimentos = 0.0
    for item in ALMOXARIFADO:
        custo = float(item.get("custoPorcao") or 0)
        usos = item.get("usos") or []
        if so_mes:
            mantimentos += sum(custo for uso in usos if do_mes(uso))
        else:
            mantimentos += custo * len(usos)
    custos = motoboy + diarias + reserva + prolabore + ocupacao + ifood + noventa + mantimentos
    return {
        "bruto": round(bruto, 2),
        "juros": round(juros, 2),
        "motoboy": round(motoboy, 2),
        "diarias": round(diarias, 2),
        "reserva": round(reserva, 2),
        "prolabore": round(prolabore, 2),
        "ocupacao": round(ocupacao, 2),
        "ifood": round(ifood, 2),
        "noventa": round(noventa, 2),
        "mantimentos": round(mantimentos, 2),
        "liquido": round(bruto - custos, 2),
        "metaMes": float(ADMIN.get("metaMes") or 0),
    }


@app.get("/api/financeiro")
def listar_financeiro():
    return list(reversed(LIVRO_CAIXA))


@app.get("/api/financeiro/resumo")
def financeiro_resumo():
    return {
        "mes": resumo_periodo(True),
        "geral": resumo_periodo(False),
        "taxas": list(reversed(TAXAS_PAGAS)),
        "folha": list(reversed(FOLHA)),
    }


class NovaTaxa(BaseModel):
    canal: str
    valor: float
    observacao: str = ""


@app.post("/api/taxas", status_code=201)
def lancar_taxa(payload: NovaTaxa):
    canal = payload.canal.strip().upper()
    if canal not in ("MOTOBOY", "IFOOD", "NOVENTA"):
        raise HTTPException(status_code=400, detail="Escolha motoboy, iFood ou 99Food.")
    if payload.valor <= 0:
        raise HTTPException(status_code=400, detail="Informe o valor pago.")
    taxa = {
        "id": f"TX-{uuid.uuid4().hex[:6].upper()}",
        "canal": canal,
        "valor": round(payload.valor, 2),
        "observacao": payload.observacao.strip(),
        "criadoEm": agora_texto(),
    }
    TAXAS_PAGAS.append(taxa)
    salvar()
    return taxa


@app.delete("/api/taxas/{taxa_id}")
def apagar_taxa(taxa_id: str):
    antes = len(TAXAS_PAGAS)
    TAXAS_PAGAS[:] = [taxa for taxa in TAXAS_PAGAS if taxa["id"] != taxa_id]
    if len(TAXAS_PAGAS) == antes:
        raise HTTPException(status_code=404, detail="Essa taxa não está lançada.")
    salvar()
    return {"ok": True}


class ContaMotoboy(BaseModel):
    salario: float = 0
    regime: str = "SIMPLES"
    rat: float = 2
    sistemaS: float = 5.8
    valeTransporte: float = 0
    valeAlimentacao: float = 0
    dependentes: int = 0
    nome: str = ""
    pctValeTransporte: float = 6
    pctValeAlimentacao: float = 20
    tetoDescontos: float = 70
    pctFgts: float = 8
    pctFerias: float = 11.11
    pctDecimo: float = 8.33
    pctMulta: float = 4
    pctPatronal: float = 20
    pctEducacao: float = 2.5


class NovaDiaria(BaseModel):
    nome: str
    valor: float
    entregas: int = 0
    observacao: str = ""
    data: str = ""


def criado_da_data(data: str) -> str:
    texto = (data or "").strip()
    if texto:
        try:
            dia = datetime.strptime(texto, "%Y-%m-%d")
            return dia.strftime("%d/%m/%Y") + " " + datetime.now().strftime("%H:%M")
        except ValueError:
            pass
    return agora_texto()


@app.post("/api/motoboy/conta")
def conta_motoboy(payload: ContaMotoboy):
    return calcular_motoboy(
        payload.salario,
        payload.regime,
        payload.rat,
        payload.sistemaS,
        payload.valeTransporte,
        payload.valeAlimentacao,
        payload.dependentes,
        pct_vt=payload.pctValeTransporte,
        pct_va=payload.pctValeAlimentacao,
        teto_descontos=payload.tetoDescontos,
        pct_fgts=payload.pctFgts,
        pct_ferias=payload.pctFerias,
        pct_decimo=payload.pctDecimo,
        pct_multa=payload.pctMulta,
        pct_patronal=payload.pctPatronal,
        pct_educacao=payload.pctEducacao,
    )


@app.post("/api/motoboy/diaria", status_code=201)
def lancar_diaria(payload: NovaDiaria):
    nome = payload.nome.strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do motoboy.")
    if payload.valor <= 0:
        raise HTTPException(status_code=400, detail="Informe o valor da diária.")
    item = {
        "id": f"MB-{uuid.uuid4().hex[:6].upper()}",
        "tipo": "DIARIA",
        "nome": nome,
        "valor": round(payload.valor, 2),
        "entregas": max(int(payload.entregas or 0), 0),
        "observacao": payload.observacao.strip(),
        "criadoEm": criado_da_data(payload.data),
    }
    FOLHA.append(item)
    salvar()
    return item


@app.post("/api/motoboy/reserva", status_code=201)
def lancar_reserva(payload: ContaMotoboy):
    nome = payload.nome.strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do motoboy.")
    if payload.salario <= 0:
        raise HTTPException(status_code=400, detail="Informe o salário bruto.")
    conta = calcular_motoboy(
        payload.salario,
        payload.regime,
        payload.rat,
        payload.sistemaS,
        payload.valeTransporte,
        payload.valeAlimentacao,
        payload.dependentes,
        False,
        pct_vt=payload.pctValeTransporte,
        pct_va=payload.pctValeAlimentacao,
        teto_descontos=payload.tetoDescontos,
        pct_fgts=payload.pctFgts,
        pct_ferias=payload.pctFerias,
        pct_decimo=payload.pctDecimo,
        pct_multa=payload.pctMulta,
        pct_patronal=payload.pctPatronal,
        pct_educacao=payload.pctEducacao,
    )
    quando = agora_texto()
    competencia = quando[3:10]
    item = next(
        (
            atual
            for atual in FOLHA
            if atual.get("tipo") == "RESERVA" and str(atual.get("criadoEm", ""))[3:10] == competencia
        ),
        None,
    )
    if item is None:
        item = {"id": f"MB-{uuid.uuid4().hex[:6].upper()}", "tipo": "RESERVA"}
        FOLHA.append(item)
    item.update(conta)
    item["tipo"] = "RESERVA"
    item["nome"] = nome
    item["criadoEm"] = quando
    salvar()
    return item


@app.delete("/api/motoboy/{item_id}")
def apagar_folha(item_id: str):
    antes = len(FOLHA)
    FOLHA[:] = [item for item in FOLHA if item.get("id") != item_id]
    if len(FOLHA) == antes:
        raise HTTPException(status_code=404, detail="Esse lançamento do motoboy não está na lista.")
    salvar()
    return {"ok": True}


class PlanoProlabore(BaseModel):
    moradia: float = 0
    saude: float = 0
    educacao: float = 0
    alimentacao: float = 0
    outrasPessoais: float = 0
    metaPessoal: float = 0
    mercado: float = 0
    aluguel: float = 0
    contasLoja: float = 0
    contador: float = 0
    outrasLoja: float = 0
    prolaboreFixo: float = 0
    reservaPfGuardada: float = 0
    dependentes: int = 0
    dia: int = 5
    calendario: str = "TRIMESTRAL"
    pctDistribuir: float = 50
    pctInss: float = 11
    mesesReservaPj: int = 3
    mesesReservaPf: int = 6
    regime: str = "SIMPLES"
    rat: float = 2
    sistemaS: float = 5.8
    pctPatronal: float = 20
    pctEducacao: float = 2.5
    tetoDescontos: float = 70
    liquidoMes: float = 0
    reservaContratado: float = 0
    mensalidades: float = 0
    saldoLoja: float = 0
    lancar: bool = False


@app.post("/api/admin/prolabore")
def gravar_prolabore(payload: PlanoProlabore, request: Request):
    exigir_admin(request)
    valores = (
        payload.moradia, payload.saude, payload.educacao, payload.alimentacao, payload.outrasPessoais,
        payload.metaPessoal, payload.mercado, payload.aluguel, payload.contasLoja, payload.contador,
        payload.outrasLoja, payload.prolaboreFixo, payload.reservaPfGuardada, payload.liquidoMes,
        payload.reservaContratado, payload.mensalidades, payload.saldoLoja,
    )
    if min(valores) < 0 or payload.dependentes < 0:
        raise HTTPException(status_code=400, detail="Os valores não podem ser negativos.")
    calendario = payload.calendario.strip().upper()
    if calendario not in ("TRIMESTRAL", "SEMESTRAL", "ANUAL", "NENHUM"):
        raise HTTPException(status_code=400, detail="A distribuição é trimestral, semestral, anual ou nenhuma.")
    if payload.dia < 1 or payload.dia > 28:
        raise HTTPException(status_code=400, detail="O dia do pró-labore fica entre 1 e 28.")
    custo_vida = round(
        payload.moradia + payload.saude + payload.educacao + payload.alimentacao + payload.outrasPessoais + payload.metaPessoal,
        2,
    )
    fixos = round(payload.aluguel + payload.contasLoja + payload.contador + payload.outrasLoja, 2)
    conta = calcular_prolabore(
        custo_vida,
        payload.mercado,
        payload.prolaboreFixo,
        payload.liquidoMes,
        fixos,
        payload.saldoLoja,
        payload.reservaPfGuardada,
        payload.reservaContratado,
        payload.mensalidades,
        payload.regime,
        payload.rat,
        payload.sistemaS,
        payload.dependentes,
        payload.pctInss,
        payload.tetoDescontos,
        payload.pctPatronal,
        payload.pctEducacao,
        payload.mesesReservaPj,
        payload.mesesReservaPf,
        payload.pctDistribuir,
        calendario,
        payload.dia,
    )
    if payload.lancar and conta["prolabore"] <= 0:
        raise HTTPException(status_code=400, detail="Informe o custo de vida, o valor de mercado ou o pró-labore fixo.")
    ADMIN["prolabore"] = {
        "moradia": round(payload.moradia, 2),
        "saude": round(payload.saude, 2),
        "educacao": round(payload.educacao, 2),
        "alimentacao": round(payload.alimentacao, 2),
        "outrasPessoais": round(payload.outrasPessoais, 2),
        "metaPessoal": round(payload.metaPessoal, 2),
        "mercado": round(payload.mercado, 2),
        "aluguel": round(payload.aluguel, 2),
        "contasLoja": round(payload.contasLoja, 2),
        "contador": round(payload.contador, 2),
        "outrasLoja": round(payload.outrasLoja, 2),
        "prolaboreFixo": round(payload.prolaboreFixo, 2),
        "reservaPfGuardada": round(payload.reservaPfGuardada, 2),
        "dependentes": max(int(payload.dependentes or 0), 0),
        "dia": min(max(int(payload.dia), 1), 28),
        "calendario": calendario,
        "pctDistribuir": taxa_folha(payload.pctDistribuir, 50),
        "pctInss": taxa_folha(payload.pctInss, 11),
        "mesesReservaPj": min(max(int(payload.mesesReservaPj), 3), 6),
        "mesesReservaPf": min(max(int(payload.mesesReservaPf), 6), 12),
        "regime": regime_motoboy(payload.regime),
    }
    if payload.lancar:
        quando = agora_texto()
        competencia = quando[3:10]
        item = next(
            (
                atual
                for atual in FOLHA
                if atual.get("tipo") == "PROLABORE" and str(atual.get("criadoEm", ""))[3:10] == competencia
            ),
            None,
        )
        if item is None:
            item = {"id": f"MB-{uuid.uuid4().hex[:6].upper()}", "tipo": "PROLABORE"}
            FOLHA.append(item)
        item.update(conta)
        item["tipo"] = "PROLABORE"
        item["nome"] = "Pró-labore"
        item["criadoEm"] = quando
    salvar()
    return {"ok": True, "prolabore": prolabore_publico(), "conta": conta}


class ContaCasaItem(BaseModel):
    valor: float = 0
    dia: int = 10
    forma: str = "PIX"
    cartao: str = ""
    pagador: str = "CASA"
    nome: str = ""


class CartaoCasa(BaseModel):
    id: str = ""
    nome: str = ""
    final: str = ""
    limite: float = 0
    fecha: int = 1
    vence: int = 10
    dono: str = "CASA"


class PlanoCasa(BaseModel):
    areaTotal: float = 0
    areaLoja: float = 0
    pctAluguel: float = 30
    kwhConta: float = 0
    kwhLoja: float = 0
    pctLuz: float = 70
    pctAgua: float = 55
    gasModo: str = "BOTIJAO"
    pctGas: float = 65
    pctInternet: float = 50
    pctTelefone: float = 50
    telefoneExclusivo: bool = False
    receitas: float = 0
    saldoPessoal: float = 0
    cartoes: list[CartaoCasa] = Field(default_factory=list)
    contas: dict[str, ContaCasaItem] = Field(default_factory=dict)
    lancar: bool = False


class AvisoCasa(BaseModel):
    imagem: str = ""
    texto: str = ""


def _casa_dict(payload: PlanoCasa) -> dict:
    return {
        "areaTotal": payload.areaTotal,
        "areaLoja": payload.areaLoja,
        "pctAluguel": payload.pctAluguel,
        "kwhConta": payload.kwhConta,
        "kwhLoja": payload.kwhLoja,
        "pctLuz": payload.pctLuz,
        "pctAgua": payload.pctAgua,
        "gasModo": payload.gasModo,
        "pctGas": payload.pctGas,
        "pctInternet": payload.pctInternet,
        "pctTelefone": payload.pctTelefone,
        "telefoneExclusivo": payload.telefoneExclusivo,
        "receitas": payload.receitas,
        "saldoPessoal": payload.saldoPessoal,
        "cartoes": [cartao.model_dump() if hasattr(cartao, "model_dump") else cartao.dict() for cartao in payload.cartoes],
        "contas": {
            chave: (item.model_dump() if hasattr(item, "model_dump") else item.dict())
            for chave, item in payload.contas.items()
        },
    }


@app.post("/api/admin/casa/aviso")
def ler_aviso_casa(payload: AvisoCasa, request: Request):
    exigir_admin(request)
    texto = (payload.texto or "").strip()
    bruto = payload.imagem.split(",", 1)[1] if "," in payload.imagem else payload.imagem
    if len(bruto) > 5_500_000:
        raise HTTPException(status_code=400, detail="A foto do aviso está grande demais.")
    if bruto:
        try:
            conteudo = base64.b64decode(bruto, validate=False)
        except (ValueError, TypeError):
            conteudo = b""
        if len(conteudo) > 4_000_000:
            raise HTTPException(status_code=400, detail="A foto do aviso está grande demais.")
        lido = ler_imagem_aviso(conteudo)
        if lido:
            texto = f"{texto}\n{lido}".strip()
    return {"ok": True, "texto": texto}


def _extensao_imagem(conteudo: bytes) -> str:
    if conteudo.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(conteudo) >= 12 and conteudo.startswith(b"RIFF") and conteudo[8:12] == b"WEBP":
        return "webp"
    return ""


def _pasta_do_lado(raiz: str, quando: datetime) -> str:
    pasta = os.path.abspath(os.path.join(raiz, quando.strftime("%Y-%m")))
    base = os.path.abspath(raiz)
    if os.path.commonpath([pasta, base]) != base:
        raise HTTPException(status_code=400, detail="A pasta do arquivo não pôde ser aberta.")
    os.makedirs(pasta, exist_ok=True)
    return pasta


def _ficha_lado(lado: str, nome: str, pago_para: str, forma: str, pagador: str, valor: float, deste: float, outro: float, quando: datetime, comprovante: str) -> dict:
    return {
        "lado": lado,
        "conta": nome,
        "pagoPara": pago_para,
        "forma": forma,
        "pagador": pagador,
        "valorCheio": round(valor, 2),
        "valorDesteLado": round(deste, 2),
        "outroLado": round(outro, 2),
        "quando": quando.strftime("%d/%m/%Y %H:%M"),
        "comprovante": comprovante,
    }


def _escrever_lado(raiz: str, lado: str, base: str, ficha: dict, conteudo: bytes, extensao: str, quando: datetime) -> str:
    pasta = _pasta_do_lado(raiz, quando)
    comprovante = ""
    if conteudo and extensao:
        comprovante = f"{base}.{extensao}"
        with open(os.path.join(pasta, comprovante), "wb") as arquivo:
            arquivo.write(conteudo)
    ficha = dict(ficha)
    ficha["comprovante"] = comprovante
    ficha["lado"] = lado
    with open(os.path.join(pasta, f"{base}.json"), "w", encoding="utf-8") as arquivo:
        json.dump(ficha, arquivo, ensure_ascii=False, indent=2)
    return pasta


class ComprovanteCasa(BaseModel):
    conta: str = ""
    pagoPara: str = ""
    forma: str = "PIX"
    pagador: str = "CASA"
    valor: float = 0
    pf: float = 0
    loja: float = 0
    imagem: str = ""


@app.post("/api/admin/casa/arquivo")
def arquivar_comprovante(payload: ComprovanteCasa, request: Request):
    exigir_admin(request)
    conta = payload.conta.strip()
    conhecidas = dict(CONTAS_CASA)
    if conta not in conhecidas:
        raise HTTPException(status_code=400, detail="Escolha a conta deste pagamento.")
    forma = payload.forma.strip().upper()
    if forma not in FORMAS_CASA:
        raise HTTPException(status_code=400, detail="Escolha PIX, dinheiro, débito, crédito ou boleto.")
    if payload.valor <= 0 or payload.pf < 0 or payload.loja < 0:
        raise HTTPException(status_code=400, detail="O valor do aviso precisa ser maior que zero.")
    valor = round(payload.valor, 2)
    if conhecidas[conta]:
        pf = round(payload.pf, 2)
        loja = round(payload.loja, 2)
        if abs((pf + loja) - valor) > 0.02:
            raise HTTPException(status_code=400, detail="A parte da casa e a parte da loja precisam fechar o valor do aviso.")
    else:
        pf = valor
        loja = 0.0
    pagador = "LOJA" if payload.pagador.strip().upper() == "LOJA" else "CASA"
    bruto = payload.imagem.split(",", 1)[1] if "," in payload.imagem else payload.imagem
    conteudo = b""
    if bruto:
        if len(bruto) > 5_500_000:
            raise HTTPException(status_code=400, detail="A foto do aviso está grande demais.")
        try:
            conteudo = base64.b64decode(bruto, validate=False)
        except (ValueError, TypeError):
            conteudo = b""
        if len(conteudo) > 4_000_000:
            raise HTTPException(status_code=400, detail="A foto do aviso está grande demais.")
    extensao = _extensao_imagem(conteudo) if conteudo else ""
    if conteudo and not extensao:
        conteudo = b""
    quando = datetime.now()
    base_nome = f"{quando.strftime('%Y-%m-%d_%H%M%S')}_{conta}"
    nome = NOMES_CONTAS.get(conta, conta)
    pago_para = payload.pagoPara.strip()[:80]
    ficha = _ficha_lado("", nome, pago_para, forma, pagador, valor, 0, 0, quando, "")
    fisica = ""
    juridica = ""
    if pf > 0:
        ficha_pf = dict(ficha)
        ficha_pf["valorDesteLado"] = pf
        ficha_pf["outroLado"] = loja
        fisica = _escrever_lado(PASTA_FISICA, "PESSOA_FISICA", base_nome, ficha_pf, conteudo, extensao, quando)
    if loja > 0:
        ficha_pj = dict(ficha)
        ficha_pj["valorDesteLado"] = loja
        ficha_pj["outroLado"] = pf
        juridica = _escrever_lado(PASTA_JURIDICA, "PESSOA_JURIDICA", base_nome, ficha_pj, conteudo, extensao, quando)
    return {"ok": True, "fisica": bool(fisica), "juridica": bool(juridica)}


def arquivar_controle_mes(dados: dict, conta: dict) -> None:
    quando = datetime.now()
    contas = dados.get("contas") or {}

    def linhas(campo: str) -> list[dict]:
        saida = []
        for item in conta.get("itens") or []:
            deste = round(float(item.get(campo) or 0), 2)
            if deste <= 0:
                continue
            origem = contas.get(item["id"]) or {}
            forma = str(origem.get("forma") or "PIX").upper()
            if forma not in FORMAS_CASA:
                forma = "PIX"
            outro = round(float(item.get("loja" if campo == "pf" else "pf") or 0), 2)
            saida.append({
                "conta": NOMES_CONTAS.get(item["id"], item["id"]),
                "pagoPara": str(origem.get("nome") or "").strip()[:80],
                "forma": forma,
                "pagador": item.get("pagador") or "CASA",
                "valorCheio": round(float(item.get("bruto") or 0), 2),
                "valorDesteLado": deste,
                "outroLado": outro,
            })
        return saida

    def cartoes_de(dono: str) -> list[dict]:
        saida = []
        for cartao in dados.get("cartoes") or []:
            if not isinstance(cartao, dict):
                continue
            if str(cartao.get("dono") or "CASA").upper() != dono:
                continue
            final = "".join(ch for ch in str(cartao.get("final") or "") if ch.isdigit())[-4:]
            nome = str(cartao.get("nome") or "").strip()[:40]
            if len(final) != 4 or not nome:
                continue
            saida.append({"nome": nome, "final": final})
        return saida

    partes = (
        (PASTA_FISICA, "PESSOA_FISICA", linhas("pf"), cartoes_de("CASA"), round(float(conta.get("casaTotal") or 0), 2)),
        (PASTA_JURIDICA, "PESSOA_JURIDICA", linhas("loja"), cartoes_de("LOJA"), round(float(conta.get("lojaTotal") or 0), 2)),
    )
    for raiz, lado, itens, cartoes, total in partes:
        if not itens and not cartoes:
            continue
        pasta = _pasta_do_lado(raiz, quando)
        with open(os.path.join(pasta, "controle.json"), "w", encoding="utf-8") as arquivo:
            json.dump(
                {
                    "lado": lado,
                    "mes": quando.strftime("%m/%Y"),
                    "total": total,
                    "contas": itens,
                    "cartoes": cartoes,
                    "quando": quando.strftime("%d/%m/%Y %H:%M"),
                },
                arquivo,
                ensure_ascii=False,
                indent=2,
            )


@app.post("/api/admin/casa")
def gravar_casa(payload: PlanoCasa, request: Request):
    exigir_admin(request)
    numeros = (
        payload.areaTotal, payload.areaLoja, payload.kwhConta, payload.kwhLoja,
        payload.receitas, payload.saldoPessoal,
    )
    if min(numeros) < 0 or any(item.valor < 0 or item.dia < 0 for item in payload.contas.values()):
        raise HTTPException(status_code=400, detail="Os valores não podem ser negativos.")
    if any(cartao.limite < 0 for cartao in payload.cartoes):
        raise HTTPException(status_code=400, detail="Os valores não podem ser negativos.")
    dados = _casa_dict(payload)
    conta = calcular_casa(dados)
    if payload.lancar and conta["lojaTotal"] <= 0:
        raise HTTPException(status_code=400, detail="A parte da loja ainda está zerada.")
    ADMIN["casa"] = dados
    ADMIN["casa"] = casa_publica()
    arquivar_controle_mes(ADMIN["casa"], conta)
    if payload.lancar:
        quando = agora_texto()
        competencia = quando[3:10]
        item = next(
            (
                atual
                for atual in FOLHA
                if atual.get("tipo") == "OCUPACAO" and str(atual.get("criadoEm", ""))[3:10] == competencia
            ),
            None,
        )
        if item is None:
            item = {"id": f"MB-{uuid.uuid4().hex[:6].upper()}"}
            FOLHA.append(item)
        ident = item["id"]
        item.clear()
        item.update({
            "id": ident,
            "tipo": "OCUPACAO",
            "nome": "Custo da loja",
            "custoLoja": conta["lojaTotal"],
            "aluguelLoja": conta["aluguelLoja"],
            "contasLoja": conta["contasLoja"],
            "transferencia": conta["transferencia"],
            "sentido": conta["sentido"],
            "criadoEm": quando,
        })
    salvar()
    return {"ok": True, "casa": casa_publica(), "conta": conta}


class NovoMantimento(BaseModel):
    cupom: str
    item: str
    valor: float
    quantidade: float
    unidade: str = "g"
    uso: float


@app.get("/api/almoxarifado")
def listar_almoxarifado():
    return list(reversed(ALMOXARIFADO))


@app.post("/api/almoxarifado", status_code=201)
def criar_mantimento(payload: NovoMantimento):
    cupom = payload.cupom.strip() or "sem nota"
    item = payload.item.strip()
    if not item:
        raise HTTPException(status_code=400, detail="Escolha o mantimento ou escreva o nome.")
    if payload.valor < 0 or payload.quantidade <= 0 or payload.uso <= 0:
        raise HTTPException(status_code=400, detail="Informe quanto pagou, quanto comprou e quanto entra numa receita.")
    if payload.uso > payload.quantidade:
        raise HTTPException(status_code=400, detail="O que entra numa receita não pode passar da quantidade comprada.")
    rendimento = math.floor(payload.quantidade / payload.uso)
    if rendimento < 1:
        raise HTTPException(status_code=400, detail="Essa quantidade não completa nem uma receita.")
    custo = round(payload.valor / rendimento, 2)
    sobra = round(payload.quantidade - (rendimento * payload.uso), 2)
    registro = {
        "id": f"ALM-{uuid.uuid4().hex[:6].upper()}",
        "cupom": cupom,
        "item": item,
        "valor": round(payload.valor, 2),
        "quantidade": payload.quantidade,
        "unidade": payload.unidade.strip() or "g",
        "uso": payload.uso,
        "rendimento": rendimento,
        "sobra": sobra,
        "custoPorcao": custo,
        "usos": [],
        "criadoEm": agora_texto(),
    }
    ALMOXARIFADO.append(registro)
    salvar()
    return registro


@app.post("/api/almoxarifado/{item_id}/usar")
def usar_mantimento(item_id: str):
    item = next((entrada for entrada in ALMOXARIFADO if entrada["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Esse mantimento não está no depósito.")
    if len(item.get("usos") or []) >= int(item["rendimento"]):
        raise HTTPException(status_code=400, detail="Esse mantimento já foi todo usado.")
    item.setdefault("usos", []).append(agora_texto())
    salvar()
    return item


@app.delete("/api/almoxarifado/{item_id}")
def apagar_mantimento(item_id: str):
    antes = len(ALMOXARIFADO)
    ALMOXARIFADO[:] = [item for item in ALMOXARIFADO if item["id"] != item_id]
    if len(ALMOXARIFADO) == antes:
        raise HTTPException(status_code=404, detail="Esse mantimento não está no depósito.")
    salvar()
    return {"ok": True}


class EntradaAdmin(BaseModel):
    senha: str


class TrocaSenha(BaseModel):
    senhaAtual: str
    senhaNova: str


class DadosBanco(BaseModel):
    empresaSaldo: float = 0
    empresaLimite: float = 0
    empresaCartaoUsado: float = 0
    nubankSaldo: float = 0
    metaMes: float = 0
    cartaoVencimento: int = 0
    ifoodSaldo: float = 0
    ifoodForma: str = "PIX"
    ifoodTaxa: float = 0
    ifoodPlano: str = "BASICO"
    ifoodPagamento: str = "APP"
    ifoodComissao: float = 12
    ifoodTaxaPagamento: float = 3.2
    ifoodMensalidade: float = 110
    ifoodIsencao: float = 1800
    ifoodAntecipacao: str = "NENHUMA"
    ifoodTaxaAntecipacao: float = 0
    noventaSaldo: float = 0
    noventaForma: str = "PIX"
    noventaTaxa: float = 0
    noventaPlano: str = "PARCEIRA"
    noventaPagamento: str = "APP"
    noventaComissao: float = 8.9
    noventaTaxaPagamento: float = 3.2
    noventaLogistica: float = 0
    noventaMensalidade: float = 0
    noventaRepasse: str = "NENHUMA"
    noventaTaxaSaque: float = 0
    ifoodConfirmado: bool = False
    noventaConfirmado: bool = False
    bancoConfirmado: bool = False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def email_valido(texto: str) -> str:
    email = (texto or "").strip().lower()
    if "@" not in email or "." not in email.split("@")[-1] or " " in email:
        return ""
    return email


def falha_de_senha(request: Request) -> None:
    FALHAS_SENHA["n"] += 1
    if FALHAS_SENHA["n"] < 3:
        raise HTTPException(status_code=401, detail="E-mail ou senha não conferem.")
    FALHAS_SENHA["n"] = 0
    FALHAS_SENHA["ate"] = time.time() + 60
    enviou = disparar_redefinicao(request) if ADMIN.get("email") else False
    if enviou:
        raise HTTPException(status_code=429, detail="Três senhas não bateram. O link para criar uma senha nova foi para o e-mail da loja.")
    raise HTTPException(status_code=429, detail="Três senhas não bateram. Espere um minuto e tente de novo.")


def disparar_redefinicao(request: Request) -> bool:
    destino = email_valido(ADMIN.get("email") or "")
    if not destino:
        return False
    token = secrets.token_urlsafe(24)
    ADMIN["resetHash"] = hash_token(token)
    ADMIN["resetAte"] = time.time() + 30 * 60
    salvar()
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return False
    link = f"{base_publica(request)}/redefinir?token={quote(token)}"
    mensagem = EmailMessage()
    mensagem["Subject"] = "Caminho dos Doces — nova senha do PDV"
    mensagem["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", destino))
    mensagem["To"] = destino
    mensagem.set_content(
        "Três senhas não bateram no PDV da loja.\n\n"
        "Abra este link neste computador para criar uma senha nova. Ele vale por 30 minutos.\n\n"
        f"{link}\n"
    )
    try:
        porta = int(os.getenv("SMTP_PORT", "587"))
        with smtplib.SMTP(host, porta, timeout=15) as correio:
            if os.getenv("SMTP_TLS", "1") != "0":
                correio.starttls()
            usuario = os.getenv("SMTP_USER", "")
            segredo = os.getenv("SMTP_SENHA", "")
            if usuario:
                correio.login(usuario, segredo)
            correio.send_message(mensagem)
        return True
    except (OSError, smtplib.SMTPException, ValueError):
        return False


class LoginLoja(BaseModel):
    email: str
    senha: str


class RedefinirSenha(BaseModel):
    token: str
    senhaNova: str


def _sessao_valida(request: Request) -> str:
    token = request.cookies.get("loja") or request.headers.get("x-admin") or ""
    validade = TOKENS_ADMIN.get(token)
    if not validade or validade < time.time():
        TOKENS_ADMIN.pop(token, None)
        return ""
    return token


@app.get("/api/login/sessao")
def sessao_loja(request: Request):
    token = _sessao_valida(request)
    if not token:
        raise HTTPException(status_code=401, detail="Entre com o e-mail e a senha da loja.")
    return {"ok": True, "token": token}


@app.post("/api/login")
def login_loja(payload: LoginLoja, request: Request):
    if time.time() < FALHAS_SENHA["ate"]:
        raise HTTPException(status_code=429, detail="Três senhas não bateram. Espere um minuto ou abra o link enviado ao e-mail.")
    email = email_valido(payload.email)
    if not email:
        raise HTTPException(status_code=400, detail="Escreva o e-mail da loja.")
    guardado = email_valido(ADMIN.get("email") or "")
    if guardado and email != guardado:
        falha_de_senha(request)
    if not senha_confere(payload.senha):
        falha_de_senha(request)
    if not guardado:
        ADMIN["email"] = email
        salvar()
    FALHAS_SENHA["n"] = 0
    token = secrets.token_urlsafe(24)
    TOKENS_ADMIN[token] = time.time() + 12 * 3600
    resposta = JSONResponse({"ok": True, "token": token})
    resposta.set_cookie("loja", token, httponly=True, samesite="lax", max_age=12 * 3600, path="/")
    return resposta


@app.post("/api/login/sair")
def sair_loja(request: Request):
    token = request.cookies.get("loja") or ""
    TOKENS_ADMIN.pop(token, None)
    resposta = JSONResponse({"ok": True})
    resposta.delete_cookie("loja", path="/")
    return resposta


@app.post("/api/login/redefinir")
def redefinir_senha(payload: RedefinirSenha):
    nova = payload.senhaNova.strip()
    if len(nova) < 6:
        raise HTTPException(status_code=400, detail="A nova senha precisa ter pelo menos 6 caracteres.")
    guardado = ADMIN.get("resetHash") or ""
    ate = float(ADMIN.get("resetAte") or 0)
    if not guardado or ate < time.time() or not secrets.compare_digest(hash_token(payload.token.strip()), guardado):
        raise HTTPException(status_code=400, detail="Esse link já venceu. Erre a senha três vezes para receber outro.")
    salt = secrets.token_hex(16)
    ADMIN["salt"] = salt
    ADMIN["senha"] = hash_senha(nova, salt)
    ADMIN["resetHash"] = ""
    ADMIN["resetAte"] = 0
    FALHAS_SENHA["n"] = 0
    FALHAS_SENHA["ate"] = 0
    salvar()
    return {"ok": True}


@app.get("/redefinir", response_class=HTMLResponse)
def pagina_redefinir(token: str = ""):
    seguro = escape(token)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nova senha — Caminho dos Doces</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    body {{ margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(160deg, #F7D5E2, #D7F0F2 55%, #D5DCF0); font-family: Poppins, sans-serif; color: #7C4A3A; }}
    form {{ width: min(420px, calc(100% - 32px)); background: #fff; border-radius: 24px; padding: 28px 22px; box-shadow: 0 16px 40px rgba(124, 74, 58, 0.18); }}
    h1 {{ margin: 0 0 8px; font-size: 22px; }}
    p {{ margin: 0 0 14px; }}
    input {{ width: 100%; box-sizing: border-box; border: 1px solid #C5CEE6; border-radius: 12px; padding: 12px; font: inherit; }}
    button {{ width: 100%; margin-top: 14px; border: 0; border-radius: 999px; padding: 12px; background: #7C4A3A; color: #fff; font: inherit; font-weight: 700; }}
    .aviso {{ margin-top: 12px; font-weight: 600; }}
  </style>
</head>
<body>
  <form id="troca">
    <h1>Nova senha da loja</h1>
    <p>Escreva a senha nova. Ela precisa ter pelo menos 6 caracteres.</p>
    <input id="senha" type="password" autocomplete="new-password" placeholder="Senha nova">
    <button type="submit">Guardar senha nova</button>
    <div class="aviso" id="aviso"></div>
  </form>
  <script>
    document.getElementById("troca").onsubmit = async (evento) => {{
      evento.preventDefault();
      const aviso = document.getElementById("aviso");
      const resposta = await fetch("/api/login/redefinir", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ token: "{seguro}", senhaNova: document.getElementById("senha").value }})
      }});
      const corpo = await resposta.json();
      aviso.textContent = resposta.ok ? "Senha nova guardada. Volte ao PDV e entre com ela." : (corpo.detail || "Não foi possível trocar.");
    }};
  </script>
</body>
</html>"""


@app.post("/api/admin/entrar")
def entrar_admin(payload: EntradaAdmin):
    if time.time() < FALHAS_SENHA["ate"]:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Espere um minuto e tente de novo.")
    if not senha_confere(payload.senha):
        FALHAS_SENHA["n"] += 1
        if FALHAS_SENHA["n"] >= 5:
            FALHAS_SENHA["ate"] = time.time() + 60
            FALHAS_SENHA["n"] = 0
        raise HTTPException(status_code=401, detail="Senha incorreta.")
    FALHAS_SENHA["n"] = 0
    token = secrets.token_urlsafe(24)
    TOKENS_ADMIN[token] = time.time() + 12 * 3600
    return {"token": token, "bancos": admin_publico()}


FISCAL_RE = re.compile(
    r"\b(ecf|sat|fiscal|fs-?700|fs-?800|mach\s*[12]|th[\s-]?fi)\b",
    re.IGNORECASE,
)
NAO_FISCAL_RE = re.compile(
    r"(tm-?t20|tm-?t88|epson|elgin|bematech|tanca|mp-?4200|mp-?100|"
    r"pos-?58|pos-?80|t[eé]rmic|receipt|esc/?pos|datecs|gertec|control\s*id|daruma)",
    re.IGNORECASE,
)
VENDEDORES_IMPRESSORA = {"04b8": "Epson", "0b1b": "Bematech"}
USB_IGNORAR = ("root hub", "mouse", "keyboard", "bluetooth", "camera", "webcam", "linux foundation", " hub")


def classificar_impressora(nome: str) -> str:
    texto = nome or ""
    if FISCAL_RE.search(texto):
        return "FISCAL"
    if NAO_FISCAL_RE.search(texto):
        return "NAO_FISCAL"
    return "DESCONHECIDA"


def texto_impressora() -> str:
    escolha = ADMIN.get("impressora") or {}
    nome = (escolha.get("nome") or "").strip()
    tipo = escolha.get("tipo") or ""
    if not nome or tipo not in ("FISCAL", "NAO_FISCAL"):
        return ""
    if tipo == "FISCAL":
        return f"Impressora fiscal reconhecida: {nome}. Este cupom continua sem valor fiscal."
    return f"Impressora não fiscal: {nome}."


def _saida_comando(comando: list[str]) -> str:
    try:
        return subprocess.check_output(comando, text=True, stderr=subprocess.DEVNULL, timeout=4)
    except (OSError, subprocess.SubprocessError):
        return ""


def _registrar_impressora(vistas: dict, origem: str, nome: str, detalhe: str) -> None:
    nome = " ".join((nome or "").split())
    if not nome or "cups-pdf" in nome.lower():
        return
    chave = f"{origem}:{nome.lower()}"
    if chave in vistas:
        return
    vistas[chave] = {
        "id": chave,
        "nome": nome,
        "origem": origem,
        "detalhe": detalhe,
    }


def listar_impressoras() -> list[dict]:
    vistas: dict[str, dict] = {}
    for linha in _saida_comando(["lpstat", "-v"]).splitlines():
        if "device for " not in linha or ": " not in linha:
            continue
        nome, _, uri = linha.partition("device for ")[2].partition(": ")
        if "usb://" in uri or uri.startswith("parallel:") or uri.startswith("usb:"):
            _registrar_impressora(vistas, "cups", nome, uri.strip())
    for linha in _saida_comando(["lpinfo", "-v"]).splitlines():
        if "usb://" not in linha:
            continue
        uri = linha.split()[-1]
        modelo = uri.split("usb://", 1)[-1].split("?", 1)[0].replace("%20", " ")
        _registrar_impressora(vistas, "usb", modelo.replace("/", " "), uri)
    for linha in _saida_comando(["lsusb"]).splitlines():
        partes = linha.split()
        if len(partes) < 6 or ":" not in partes[5]:
            continue
        fabricante, produto = partes[5].split(":", 1)
        descricao = " ".join(partes[6:])
        if any(marca in descricao.lower() for marca in USB_IGNORAR):
            continue
        if fabricante.lower() not in VENDEDORES_IMPRESSORA and classificar_impressora(descricao) == "DESCONHECIDA":
            continue
        _registrar_impressora(vistas, "usb", descricao or VENDEDORES_IMPRESSORA.get(fabricante.lower(), descricao), f"{fabricante}:{produto}")
    escolhida = (ADMIN.get("impressora") or {}).get("id") or ""
    confirmadas = ADMIN.get("impressorasTipo") or {}
    lista = []
    for item in vistas.values():
        tipo = confirmadas.get(item["id"]) or classificar_impressora(f"{item['nome']} {item['detalhe']}")
        if tipo not in ("FISCAL", "NAO_FISCAL"):
            tipo = "DESCONHECIDA"
        lista.append({**item, "tipo": tipo, "escolhida": item["id"] == escolhida})
    lista.sort(key=lambda item: item["nome"].lower())
    return lista


class EscolhaImpressora(BaseModel):
    id: str
    nome: str
    tipo: str


@app.get("/api/impressoras")
def ler_impressoras():
    escolha = ADMIN.get("impressora") or {}
    return {
        "lista": listar_impressoras(),
        "escolhida": {
            "id": escolha.get("id") or "",
            "nome": escolha.get("nome") or "",
            "tipo": escolha.get("tipo") or "",
        },
        "fiscalLigado": emissao_fiscal_disponivel(),
    }


@app.post("/api/impressoras")
def escolher_impressora(payload: EscolhaImpressora):
    tipo = payload.tipo.strip().upper()
    nome = payload.nome.strip()
    ident = payload.id.strip()
    if tipo not in ("FISCAL", "NAO_FISCAL"):
        raise HTTPException(status_code=400, detail="Diga se ela é fiscal ou não fiscal.")
    if not ident or not nome:
        raise HTTPException(status_code=400, detail="Escolha a impressora que apareceu na lista.")
    ADMIN["impressora"] = {"id": ident, "nome": nome, "tipo": tipo}
    tipos = dict(ADMIN.get("impressorasTipo") or {})
    tipos[ident] = tipo
    ADMIN["impressorasTipo"] = tipos
    salvar()
    return ler_impressoras()


@app.get("/api/admin")
def ler_admin(request: Request):
    exigir_admin(request)
    return admin_publico()


@app.put("/api/admin")
def gravar_admin(payload: DadosBanco, request: Request):
    exigir_admin(request)
    if min(
        payload.empresaSaldo, payload.empresaLimite, payload.empresaCartaoUsado, payload.nubankSaldo,
        payload.metaMes, payload.ifoodSaldo, payload.noventaSaldo, payload.ifoodMensalidade, payload.ifoodIsencao,
        payload.noventaMensalidade,
    ) < 0:
        raise HTTPException(status_code=400, detail="Os valores não podem ser negativos.")
    if payload.empresaCartaoUsado > payload.empresaLimite:
        raise HTTPException(status_code=400, detail="O cartão não pode ter usado mais do que o limite.")
    if payload.cartaoVencimento < 0 or payload.cartaoVencimento > 31:
        raise HTTPException(status_code=400, detail="O vencimento do cartão é um dia de 1 a 31.")
    if payload.ifoodPlano not in ("BASICO", "ENTREGA"):
        raise HTTPException(status_code=400, detail="O plano do iFood é Básico ou Entrega.")
    if payload.ifoodPagamento not in ("APP", "ENTREGA"):
        raise HTTPException(status_code=400, detail="O pagamento do iFood é pelo aplicativo ou na entrega.")
    if payload.ifoodAntecipacao not in ("NENHUMA", "SEMANAL", "SEMANAL_DIGITAL", "SOB_DEMANDA"):
        raise HTTPException(status_code=400, detail="A antecipação do iFood é 30 dias, semanal, Conta Digital ou sob demanda.")
    for percentual in (payload.ifoodComissao, payload.ifoodTaxaPagamento, payload.ifoodTaxaAntecipacao):
        if percentual < 0 or percentual > 80:
            raise HTTPException(status_code=400, detail="Cada taxa do iFood fica entre 0 e 80 por cento.")
    pag_aplicada = payload.ifoodTaxaPagamento if payload.ifoodPagamento == "APP" else 0
    ant_aplicada = payload.ifoodTaxaAntecipacao if payload.ifoodPagamento == "APP" else 0
    if payload.ifoodComissao + pag_aplicada + ant_aplicada >= 100:
        raise HTTPException(status_code=400, detail="A soma das taxas do iFood precisa ficar abaixo de 100 por cento.")
    if payload.noventaPlano not in ("PARCEIRA", "PROPRIA"):
        raise HTTPException(status_code=400, detail="O plano do 99Food é entrega da 99 ou entrega da loja.")
    if payload.noventaPagamento not in ("APP", "ENTREGA"):
        raise HTTPException(status_code=400, detail="O pagamento do 99Food é pelo aplicativo ou na entrega.")
    if payload.noventaRepasse not in ("NENHUMA", "SEMANAL", "DIARIO"):
        raise HTTPException(status_code=400, detail="O repasse do 99Food é sem taxa, semanal ou diário.")
    for percentual in (payload.noventaComissao, payload.noventaTaxaPagamento, payload.noventaLogistica, payload.noventaTaxaSaque):
        if percentual < 0 or percentual > 80:
            raise HTTPException(status_code=400, detail="Cada taxa do 99Food fica entre 0 e 80 por cento.")
    pag_noventa = payload.noventaTaxaPagamento if payload.noventaPagamento == "APP" else 0
    log_noventa = payload.noventaLogistica if payload.noventaPlano == "PARCEIRA" else 0
    if payload.noventaComissao + pag_noventa + log_noventa + payload.noventaTaxaSaque >= 100:
        raise HTTPException(status_code=400, detail="A soma das taxas do 99Food precisa ficar abaixo de 100 por cento.")
    ADMIN["empresaSaldo"] = round(payload.empresaSaldo, 2)
    ADMIN["empresaLimite"] = round(payload.empresaLimite, 2)
    ADMIN["empresaCartaoUsado"] = round(payload.empresaCartaoUsado, 2)
    ADMIN["nubankSaldo"] = round(payload.nubankSaldo, 2)
    ADMIN["metaMes"] = round(payload.metaMes, 2)
    ADMIN["cartaoVencimento"] = payload.cartaoVencimento
    ADMIN["ifoodSaldo"] = round(payload.ifoodSaldo, 2)
    ADMIN["ifoodForma"] = payload.ifoodForma
    ADMIN["ifoodTaxa"] = round(payload.ifoodTaxa, 2)
    ADMIN["ifoodPlano"] = payload.ifoodPlano
    ADMIN["ifoodPagamento"] = payload.ifoodPagamento
    ADMIN["ifoodComissao"] = round(payload.ifoodComissao, 2)
    ADMIN["ifoodTaxaPagamento"] = round(payload.ifoodTaxaPagamento, 2)
    ADMIN["ifoodMensalidade"] = round(payload.ifoodMensalidade, 2)
    ADMIN["ifoodIsencao"] = round(payload.ifoodIsencao, 2)
    ADMIN["ifoodAntecipacao"] = payload.ifoodAntecipacao
    ADMIN["ifoodTaxaAntecipacao"] = round(payload.ifoodTaxaAntecipacao, 2)
    ADMIN["noventaSaldo"] = round(payload.noventaSaldo, 2)
    ADMIN["noventaForma"] = payload.noventaForma
    ADMIN["noventaTaxa"] = round(payload.noventaTaxa, 2)
    ADMIN["noventaPlano"] = payload.noventaPlano
    ADMIN["noventaPagamento"] = payload.noventaPagamento
    ADMIN["noventaComissao"] = round(payload.noventaComissao, 2)
    ADMIN["noventaTaxaPagamento"] = round(payload.noventaTaxaPagamento, 2)
    ADMIN["noventaLogistica"] = round(payload.noventaLogistica, 2)
    ADMIN["noventaMensalidade"] = round(payload.noventaMensalidade, 2)
    ADMIN["noventaRepasse"] = payload.noventaRepasse
    ADMIN["noventaTaxaSaque"] = round(payload.noventaTaxaSaque, 2)
    if payload.ifoodConfirmado:
        registrar_venda_dia("ifoodDias", "ifoodVendasEm", "ifoodCicloInicio", "ifoodCicloTipo", payload.ifoodAntecipacao, conta_ifood(ADMIN))
    if payload.noventaConfirmado:
        registrar_venda_dia("noventaDias", "noventaVendasEm", "noventaCicloInicio", "noventaCicloTipo", payload.noventaRepasse, conta_noventa(ADMIN))
    if payload.bancoConfirmado:
        ADMIN["bancoVendasEm"] = agora_texto()
    ADMIN["saldosEm"] = agora_texto()
    salvar()
    return admin_publico()


@app.put("/api/admin/senha")
def trocar_senha(payload: TrocaSenha, request: Request):
    exigir_admin(request)
    if not senha_confere(payload.senhaAtual):
        raise HTTPException(status_code=401, detail="A senha atual não confere.")
    nova = payload.senhaNova.strip()
    if len(nova) < 6:
        raise HTTPException(status_code=400, detail="A nova senha precisa ter pelo menos 6 caracteres.")
    salt = secrets.token_hex(16)
    ADMIN["salt"] = salt
    ADMIN["senha"] = hash_senha(nova, salt)
    salvar()
    return {"ok": True}


@app.post("/api/pedidos/{order_id}/cancelar")
def cancelar_pedido(order_id: str, payload: CancelamentoVenda):
    motivo = payload.motivo.strip()
    if not motivo:
        raise HTTPException(status_code=400, detail="Preencha o motivo do cancelamento.")
    pedido = next((item for item in PEDIDOS if item["orderId"] == order_id), None)
    if not pedido:
        raise HTTPException(status_code=404, detail="Essa venda não está no caixa.")
    valor = round(
        sum(
            lancamento["valor"]
            for lancamento in LIVRO_CAIXA
            if lancamento.get("orderId") == order_id and lancamento.get("tipo") == "ENTRADA"
        ),
        2,
    )
    PEDIDOS[:] = [item for item in PEDIDOS if item["orderId"] != order_id]
    LIVRO_CAIXA[:] = [
        lancamento for lancamento in LIVRO_CAIXA
        if not (lancamento.get("orderId") == order_id and lancamento.get("tipo") == "RESULTADO")
    ]
    CAIXA["saldo"] = round(CAIXA["saldo"] - valor, 2)
    CAIXA["gavetaEm"] = ""
    LIVRO_CAIXA.append({
        "id": f"CX-{uuid.uuid4().hex[:6].upper()}",
        "orderId": order_id,
        "descricao": f"Cancelamento {order_id} — {pedido['nome']}",
        "tipo": "SAIDA",
        "categoria": "CANCELAMENTO",
        "valor": valor,
        "motivo": motivo,
        "criadoEm": agora_texto(),
    })
    salvar()
    return {"caixa": CAIXA, "orderId": order_id, "motivo": motivo}


@app.get("/api/entrega/distancia")
def distancia_entrega(cep: str):
    digitos = "".join(caractere for caractere in cep if caractere.isdigit())
    if len(digitos) != 8:
        raise HTTPException(status_code=400, detail="CEP precisa ter 8 números.")
    try:
        _lat, _lng, endereco = coordenadas_do_cep(digitos)
        km = km_de_carro(_lat, _lng)
    except HTTPException:
        raise
    except (HTTPError, URLError, TimeoutError, KeyError, IndexError, ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Não foi possível medir a distância agora. Informe os km.")
    maps = (
        "https://www.google.com/maps/dir/?api=1&travelmode=driving"
        f"&origin={quote(LOJA_ORIGEM)}&destination={quote(endereco)}"
    )
    km_texto = f"{km:.1f}".replace(".", ",")
    return {
        "cep": f"{digitos[:5]}-{digitos[5:]}",
        "endereco": endereco,
        "km": km,
        "kmTexto": f"{km_texto} km",
        "maps": maps,
    }


class ReceberRestante(BaseModel):
    forma: str = "DINHEIRO"


@app.post("/api/pedidos/{order_id}/restante")
def receber_restante(order_id: str, payload: ReceberRestante, request: Request):
    if CAIXA["status"] != "ABERTO":
        raise HTTPException(status_code=400, detail="Abra o caixa para receber o restante.")
    pedido = next((item for item in PEDIDOS if item["orderId"] == order_id), None)
    if not pedido:
        raise HTTPException(status_code=404, detail="Essa venda não está na agenda.")
    restante = round(float(pedido.get("restante") or 0), 2)
    if restante <= 0:
        raise HTTPException(status_code=400, detail="Essa venda já está quitada.")
    formas = {"DINHEIRO": "Dinheiro", "PIX": "PIX", "DEBITO": "Débito"}
    forma = formas.get((payload.forma or "").strip().upper())
    if not forma:
        raise HTTPException(status_code=400, detail="Escolha dinheiro, PIX ou débito.")
    pedido["restante"] = 0.0
    pedido["sinal"] = round(float(pedido.get("sinal") or 0) + restante, 2)
    pedido["statusPagamento"] = "PAGO"
    pedido["lembrete"] = ""
    pedido.setdefault("partes", []).append({"forma": f"{forma} na entrega", "valor": restante})
    pedido["pagamento"] = f"{pedido.get('pagamento') or ''} + {forma} na entrega".strip(" +")
    LIVRO_CAIXA.append({
        "id": f"CX-{uuid.uuid4().hex[:6].upper()}",
        "orderId": order_id,
        "descricao": f"RESTANTE {order_id} — {pedido.get('nome') or ''}",
        "tipo": "ENTRADA",
        "categoria": "RESTANTE",
        "valor": restante,
        "criadoEm": agora_texto(),
    })
    CAIXA["saldo"] = round(float(CAIXA.get("saldo") or 0) + restante, 2)
    CAIXA["gavetaEm"] = ""
    salvar()
    return {"pedido": pedido_publico(request, pedido), "caixa": CAIXA}


@app.post("/api/pedidos", status_code=201)
def criar_pedido(payload: NovoPedido, request: Request):
    if CAIXA["status"] != "ABERTO":
        raise HTTPException(status_code=400, detail="O caixa está fechado.")
    if not payload.telefone.strip():
        raise HTTPException(status_code=400, detail="Informe o telefone.")
    payload.nome = nome_e_sobrenome(payload.nome)
    payload.cpf = cpf_formatado(payload.cpf)
    if not payload.items:
        raise HTTPException(status_code=400, detail="Adicione pelo menos um doce.")

    subtotal = round(sum(i.quantity * i.unitPrice for i in payload.items), 2)
    entrega = payload.entrega.strip()
    distancia = round(max(payload.distanciaKm, 0), 2)
    if entrega in ENTREGAS_DA_LOJA:
        taxa = calcular_taxa_entrega(entrega, distancia)
        taxa_controle = 0.0
    elif entrega == "Uber / 99 Entregas":
        taxa = 0.0
        taxa_controle = round(max(payload.taxaControle, 0), 2)
        distancia = 0.0
    else:
        taxa = 0.0
        taxa_controle = 0.0
        distancia = 0.0
    valor_tabela = round(subtotal + taxa, 2)
    valor_cobrado = valor_tabela if payload.valorCobrado < 0 else round(max(payload.valorCobrado, 0), 2)
    resultado = round(valor_cobrado - valor_tabela, 2)
    conta = fechar_pagamento(payload, valor_cobrado)
    tipo_lancamento = "SINAL" if conta["restante"] > 0 else "VENDA"

    pedido_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    pedido = {
        "orderId": pedido_id,
        "nome": payload.nome.strip(),
        "telefone": payload.telefone.strip(),
        "cpf": payload.cpf.strip(),
        "origem": payload.origem.strip(),
        "endereco": payload.endereco.strip(),
        "cep": payload.cep.strip(),
        "dataEvento": payload.dataEvento,
        "horario": payload.horario.strip(),
        "entrega": entrega,
        "distanciaKm": distancia,
        "taxaControle": taxa_controle,
        "observacoes": payload.observacoes.strip(),
        "items": [i.model_dump() for i in payload.items],
        "subtotal": subtotal,
        "taxaEntrega": taxa,
        "valorTabela": valor_tabela,
        "valorCobrado": valor_cobrado,
        "resultado": resultado,
        "metodo": payload.pagamento,
        "total": conta["total"],
        "sinal": conta["sinal"],
        "restante": conta["restante"],
        "pagamento": conta["descricao"],
        "partes": conta["partes"],
        "statusPagamento": conta["statusPagamento"],
        "lembrete": conta["lembrete"],
        "juros": conta["juros"],
        "criadoEm": agora,
        "cupomTipo": tipo_de_cupom(payload.cupomTipo),
    }
    lancamento = {
        "id": f"CX-{uuid.uuid4().hex[:6].upper()}",
        "orderId": pedido_id,
        "descricao": f"{tipo_lancamento} {pedido_id} — {payload.nome.strip()}",
        "tipo": "ENTRADA",
        "categoria": tipo_lancamento,
        "valor": conta["sinal"],
        "criadoEm": agora,
    }
    PEDIDOS.append(pedido)
    LIVRO_CAIXA.append(lancamento)
    registrar_resultado(pedido_id, payload.nome.strip(), resultado, agora)
    CAIXA["saldo"] = round(CAIXA["saldo"] + conta["sinal"], 2)
    CAIXA["gavetaEm"] = ""
    atualizar_cliente_do_atendimento(payload)
    pedir_estoque(pedido_id)
    salvar()
    salvar_recibo(pedido)
    publicado = pedido_publico(request, pedido)
    return {
        "pedido": publicado,
        "lancamento": lancamento,
        "caixa": CAIXA,
        "envio": links_envio(publicado, publicado["link"]),
    }


if garantir_senha_admin() or garantir_conferencia_antiga():
    salvar()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORTA", "8090")))
