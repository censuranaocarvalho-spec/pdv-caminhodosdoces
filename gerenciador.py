import sys
import os
import subprocess
import socket
import time
import urllib.request
import zipfile
import shutil
import webbrowser
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette

PORTA_PDV = 8090
URL_PDV = f"http://127.0.0.1:{PORTA_PDV}/"

# Configuracao do repositorio
URL_VERSAO = "https://raw.githubusercontent.com/censuranaocarvalho-spec/pdv-caminhodosdoces/main/versao.txt"
URL_UPDATE_ZIP = "https://github.com/censuranaocarvalho-spec/pdv-caminhodosdoces/archive/refs/heads/main.zip"

def obter_raiz() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

RAIZ = obter_raiz()
PASTA_LOGS = RAIZ / "logs"
PASTA_LOGS.mkdir(exist_ok=True)

logging.basicConfig(
    filename=PASTA_LOGS / "gerenciador.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("gerenciador")

def eh_windows() -> bool:
    return sys.platform == "win32"

def comando_do_pdv():
    if eh_windows():
        main_exe = RAIZ / "main.exe"
        if main_exe.exists():
            return [str(main_exe)]
    # Fallback para desenvolvimento no Linux
    py = RAIZ / "core-orders" / "venv" / "bin" / "python"
    main_py = RAIZ / "main.py"
    if py.exists():
        return [str(py), str(main_py)]
    return [sys.executable, str(main_py)]

def esta_rodando() -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    r = sock.connect_ex(('127.0.0.1', PORTA_PDV))
    sock.close()
    return r == 0

def ler_versao_local() -> str:
    arq = RAIZ / "versao.txt"
    if not arq.exists():
        return "0.0.0"
    return arq.read_text(encoding="utf-8").strip()

def ler_versao_remota() -> str | None:
    try:
        with urllib.request.urlopen(URL_VERSAO, timeout=5) as r:
            return r.read().decode("utf-8").strip()
    except Exception as e:
        log.warning(f"Falha ao ler versao remota: {e}")
        return None

def atualizar_se_necessario(status_cb) -> bool:
    local = ler_versao_local()
    remota = ler_versao_remota()
    if remota is None:
        return False
    if remota == local:
        return False

    log.info(f"Atualizando {local} -> {remota}")
    status_cb("Baixando atualizacao...")
    zip_tmp = RAIZ / "_update.zip"
    pasta_tmp = RAIZ / "_update_tmp"

    try:
        urllib.request.urlretrieve(URL_UPDATE_ZIP, zip_tmp)
        status_cb("Extraindo...")
        if pasta_tmp.exists():
            shutil.rmtree(pasta_tmp)
        with zipfile.ZipFile(zip_tmp, "r") as z:
            z.extractall(pasta_tmp)
        sub = list(pasta_tmp.iterdir())[0]

        protegidas = {".venv", "core-orders", "logs", "dados", ".git", "main.exe", "gerenciador.exe"}
        status_cb("Aplicando atualizacao...")
        for item in sub.iterdir():
            if item.name in protegidas:
                continue
            destino = RAIZ / item.name
            if item.is_dir():
                if destino.exists():
                    shutil.rmtree(destino)
                shutil.copytree(item, destino)
            else:
                shutil.copy2(item, destino)
        return True
    except Exception as e:
        log.error(f"Falha na atualizacao: {e}")
        return False
    finally:
        if zip_tmp.exists(): zip_tmp.unlink()
        if pasta_tmp.exists(): shutil.rmtree(pasta_tmp, ignore_errors=True)

class WorkerThread(QThread):
    status_signal = pyqtSignal(str)
    concluido_signal = pyqtSignal(bool, str)

    def __init__(self, acao: str):
        super().__init__()
        self.acao = acao

    def run(self):
        if self.acao == "ligar":
            self.executar_ligar()
        elif self.acao == "desligar":
            self.executar_desligar()

    def executar_ligar(self):
        self.status_signal.emit("Verificando atualizacoes...")
        atualizar_se_necessario(lambda m: self.status_signal.emit(m))

        if not esta_rodando():
            self.status_signal.emit("Iniciando o servidor...")
            cmd = comando_do_pdv()
            log.info(f"Iniciando PDV: {' '.join(cmd)}")

            flags = 0
            if eh_windows():
                flags = subprocess.CREATE_NO_WINDOW

            try:
                subprocess.Popen(cmd, cwd=str(RAIZ), creationflags=flags)
            except Exception as e:
                log.error(f"Falha ao iniciar: {e}")
                self.concluido_signal.emit(False, f"Falha ao iniciar: {e}")
                return

           for _ in range(120):
                if esta_rodando():
                    break
                time.sleep(0.5)

        if esta_rodando():
            self.concluido_signal.emit(True, "O PDV esta ligado")
        else:
            self.concluido_signal.emit(False, "O PDV nao subiu. Veja logs/gerenciador.log")

    def executar_            for _ in range(120):
                if esta_rodando():
                    break
                time.sleep(0.5)desligar(self):
        self.status_signal.emit("Desligando...")
        if eh_windows():
            subprocess.run(["taskkill", "/F", "/IM", "main.exe"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["pkill", "-f", "main.py"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        self.concluido_signal.emit(True, "O PDV esta desligado")

class PainelPDV(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.atualizar_status()

    def init_ui(self):
        self.setWindowTitle("Caminho dos Doces")
        self.setFixedSize(420, 340)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(255, 248, 245))
        self.setPalette(palette)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.lbl_titulo = QLabel("Caminho dos Doces")
        self.lbl_titulo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lbl_titulo.setStyleSheet("color: rgb(124, 74, 58);")
        self.lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_titulo)

        self.lbl_versao = QLabel(f"Versao {ler_versao_local()}")
        self.lbl_versao.setFont(QFont("Segoe UI", 9))
        self.lbl_versao.setStyleSheet("color: rgb(160, 120, 100);")
        self.lbl_versao.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_versao)

        self.btn_ligar = QPushButton("Ligar")
        self.btn_ligar.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.btn_ligar.setFixedHeight(50)
        self.btn_ligar.setStyleSheet("QPushButton { background-color: rgb(124, 74, 58); color: white; border-radius: 6px; } QPushButton:hover { background-color: rgb(144, 84, 68); }")
        self.btn_ligar.clicked.connect(self.acao_ligar)
        layout.addWidget(self.btn_ligar)

        self.btn_desligar = QPushButton("Desligar")
        self.btn_desligar.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.btn_desligar.setFixedHeight(50)
        self.btn_desligar.setStyleSheet("QPushButton { background-color: rgb(194, 229, 233); color: rgb(124, 74, 58); border-radius: 6px; } QPushButton:hover { background-color: rgb(174, 219, 223); }")
        self.btn_desligar.clicked.connect(self.acao_desligar)
        layout.addWidget(self.btn_desligar)

        self.lbl_status = QLabel("Verificando...")
        self.lbl_status.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)
        self.setLayout(layout)

    def atualizar_status(self):
        if esta_rodando():
            self.lbl_status.setText("O PDV esta ligado")
            self.lbl_status.setStyleSheet("color: rgb(22, 101, 52);")
        else:
            self.lbl_status.setText("O PDV esta desligado")
            self.lbl_status.setStyleSheet("color: rgb(124, 74, 58);")

    def alternar_botoes(self, ativo: bool):
        self.btn_ligar.setEnabled(ativo)
        self.btn_desligar.setEnabled(ativo)

    def acao_ligar(self):
        self.alternar_botoes(False)
        self.worker = WorkerThread("ligar")
        self.worker.status_signal.connect(self.lbl_status.setText)
        self.worker.concluido_signal.connect(self.ao_concluir_ligar)
        self.worker.start()

    def ao_concluir_ligar(self, sucesso: bool, mensagem: str):
        self.alternar_botoes(True)
        self.atualizar_status()
        self.lbl_versao.setText(f"Versao {ler_versao_local()}")
        if sucesso:
            webbrowser.open(f"{URL_PDV}?v={int(time.time())}")
        else:
            QMessageBox.critical(self, "Erro", mensagem)

    def acao_desligar(self):
        self.alternar_botoes(False)
        self.worker = WorkerThread("desligar")
        self.worker.status_signal.connect(self.lbl_status.setText)
        self.worker.concluido_signal.connect(self.ao_concluir_desligar)
        self.worker.start()

    def ao_concluir_desligar(self, sucesso: bool, mensagem: str):
        self.alternar_botoes(True)
        self.atualizar_status()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    janela = PainelPDV()
    janela.show()
    sys.exit(app.exec())
