import sys
import os
import subprocess
import socket
import time
import urllib.request
import webbrowser
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

PORTA_PDV = 8090
URL_PDV = f"http://127.0.0.1:{PORTA_PDV}/"

def obter_raiz() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

RAIZ = obter_raiz()

def caminho_python_venv() -> Path:
    if sys.platform == "win32":
        return RAIZ / "core-orders" / "venv" / "Scripts" / "python.exe"
    return RAIZ / "core-orders" / "venv" / "bin" / "python"

def esta_rodando() -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    resultado = sock.connect_ex(('127.0.0.1', PORTA_PDV))
    sock.close()
    return resultado == 0

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

    
        if (RAIZ / ".git").exists():
            self.status_signal.emit("Verificando atualizações...")
            try:
                subprocess.run(
                    ["git", "-C", str(RAIZ), "pull", "--ff-only", "origin", "main"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

        if not esta_rodando():
            self.status_signal.emit("Iniciando o servidor...")
            main_py = RAIZ / "core-orders" / "main.py"
            if not main_py.exists():
                self.concluido_signal.emit(False, "Arquivo core-orders/main.py não foi encontrado.")
                return

            flags = 0
            if sys.platform == "win32":
                flags = subprocess.CREATE_NO_WINDOW

            subprocess.Popen(
                [str(py_exe), str(main_py)],
                cwd=str(RAIZ / "core-orders"),
                creationflags=flags
            )

            for _ in range(30):
                if esta_rodando():
                    break
                time.sleep(0.5)

        self.concluido_signal.emit(True, "O PDV está ligado")

    def executar_desligar(self):
        self.status_signal.emit("Desligando...")
        py_exe = caminho_python_venv()
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "python.exe"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            try:
                subprocess.run(["pkill", "-f", str(py_exe)], check=False)
            except Exception:
                pass
        time.sleep(0.5)
        self.concluido_signal.emit(True, "O PDV está desligado")

class PainelPDV(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.atualizar_status()

    def init_ui(self):
        self.setWindowTitle("Caminho dos Doces")
        self.setFixedSize(420, 320)
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

        self.lbl_nota = QLabel("Gerenciador do PDV da Loja")
        self.lbl_nota.setFont(QFont("Segoe UI", 10))
        self.lbl_nota.setStyleSheet("color: rgb(124, 74, 58);")
        self.lbl_nota.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_nota)

        self.btn_ligar = QPushButton("Ligar")
        self.btn_ligar.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.btn_ligar.setFixedHeight(50)
        self.btn_ligar.setStyleSheet("""
            QPushButton {
                background-color: rgb(124, 74, 58);
                color: white;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgb(144, 84, 68);
            }
            QPushButton:disabled {
                background-color: rgb(200, 180, 175);
            }
        """)
        self.btn_ligar.clicked.connect(self.acao_ligar)
        layout.addWidget(self.btn_ligar)

        self.btn_desligar = QPushButton("Desligar")
        self.btn_desligar.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.btn_desligar.setFixedHeight(50)
        self.btn_desligar.setStyleSheet("""
            QPushButton {
                background-color: rgb(194, 229, 233);
                color: rgb(124, 74, 58);
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgb(174, 219, 223);
            }
            QPushButton:disabled {
                background-color: rgb(220, 235, 237);
            }
        """)
        self.btn_desligar.clicked.connect(self.acao_desligar)
        layout.addWidget(self.btn_desligar)

        self.lbl_status = QLabel("Verificando...")
        self.lbl_status.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        self.setLayout(layout)

    def atualizar_status(self):
        if esta_rodando():
            self.lbl_status.setText("O PDV está ligado")
            self.lbl_status.setStyleSheet("color: rgb(22, 101, 52);")
        else:
            self.lbl_status.setText("O PDV está desligado")
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
