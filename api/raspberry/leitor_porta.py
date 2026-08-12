"""
Leitor facial da porta - é ISTO que roda na Raspberry Pi.

O Pi é burro de propósito: ele só tira foto e pergunta ao servidor
"pode entrar?". Todo o reconhecimento (DeepFace/Facenet512) e toda a
regra de negócio (tem aula agora nesta sala? essa pessoa foi
convidada?) ficam no Flask. Por isso o Pi NÃO precisa de TensorFlow,
DeepFace nem pgvector - só de uma câmera e da biblioteca `requests`.

Instalação no Pi (Raspberry Pi OS Bookworm):

    sudo apt install -y python3-picamera2 python3-requests

Uso:

    python3 leitor_porta.py --chave <CHAVE> --api http://192.168.66.57:5000/api

Ou, pra não deixar a chave no histórico do shell:

    echo "<CHAVE>" > ~/.fetin_chave && chmod 600 ~/.fetin_chave
    python3 leitor_porta.py --api http://192.168.66.57:5000/api
"""

import argparse
import os
import sys
import time
from pathlib import Path

import requests

ARQUIVO_CHAVE = Path.home() / ".fetin_chave"

# Quanto tempo esperar entre uma captura e outra. Sem isso o Pi
# metralharia o servidor com dezenas de fotos por segundo - e cada
# chamada roda uma rede neural do outro lado.
INTERVALO = 2.0

# Depois de liberar alguém, para de tentar por um tempo. Evita que a
# mesma pessoa, ainda parada na frente da câmera enquanto abre a porta,
# gere uma enxurrada de logs e presenças repetidas.
PAUSA_APOS_LIBERAR = 10.0


# ------------------------------------------------------------
# Câmera
# ------------------------------------------------------------

class CameraCSI:
    """Câmera oficial do Pi (conector CSI), via picamera2."""

    def __init__(self):
        from picamera2 import Picamera2

        self.cam = Picamera2()
        # 640x480 é de sobra pro Facenet e mantém o upload leve no wi-fi.
        config = self.cam.create_still_configuration(main={"size": (640, 480)})
        self.cam.configure(config)
        self.cam.start()
        time.sleep(2)  # o sensor precisa de um tempo pra ajustar exposição

    def capturar(self) -> bytes:
        import io

        buffer = io.BytesIO()
        self.cam.capture_file(buffer, format="jpeg")
        return buffer.getvalue()

    def fechar(self):
        self.cam.stop()


class CameraUSB:
    """Webcam USB comum, via OpenCV. Alternativa se não usar a CSI."""

    def __init__(self, indice=0):
        import cv2

        self.cv2 = cv2
        self.cam = cv2.VideoCapture(indice)
        if not self.cam.isOpened():
            sys.exit(f"Não consegui abrir a câmera USB no índice {indice}.")

    def capturar(self) -> bytes:
        # Os primeiros quadros costumam vir escuros (auto-exposição).
        for _ in range(3):
            ok, frame = self.cam.read()
        if not ok:
            raise RuntimeError("Falha ao capturar quadro da câmera")
        ok, buf = self.cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("Falha ao codificar JPEG")
        return buf.tobytes()

    def fechar(self):
        self.cam.release()


def abrir_camera(tipo: str):
    if tipo == "usb":
        return CameraUSB()
    try:
        return CameraCSI()
    except ImportError:
        sys.exit(
            "picamera2 não encontrado. Instale com:\n"
            "    sudo apt install -y python3-picamera2\n"
            "Ou use uma webcam USB com --camera usb"
        )


# ------------------------------------------------------------
# Sinalização (LED / relé da fechadura)
# ------------------------------------------------------------

class Sinalizador:
    """
    Acende LED verde/vermelho nos pinos GPIO. Se a biblioteca gpiozero
    não estiver disponível (ou você ainda não ligou os LEDs), o
    programa segue funcionando e só imprime no terminal - dá pra testar
    tudo antes de encostar num fio.
    """

    def __init__(self, pino_verde=17, pino_vermelho=27):
        self.verde = self.vermelho = None
        try:
            from gpiozero import LED

            self.verde = LED(pino_verde)
            self.vermelho = LED(pino_vermelho)
            print(f"LEDs ativos (verde=GPIO{pino_verde}, vermelho=GPIO{pino_vermelho})")
        except Exception as e:
            print(f"Sem LEDs ({e.__class__.__name__}) - seguindo só com o terminal.")

    def sinalizar(self, liberado: bool, segundos=3.0):
        led = self.verde if liberado else self.vermelho
        if led is None:
            return
        led.on()
        time.sleep(segundos)
        led.off()


# ------------------------------------------------------------
# Laço principal
# ------------------------------------------------------------

def reconhecer(api: str, chave: str, imagem: bytes) -> dict:
    resposta = requests.post(
        f"{api}/faces/recognize",
        headers={"X-Device-Key": chave},
        files={"foto": ("captura.jpg", imagem, "image/jpeg")},
        timeout=60,  # a primeira chamada carrega o modelo no servidor
    )
    resposta.raise_for_status()
    return resposta.json()


def carregar_chave(informada: str | None) -> str:
    if informada:
        return informada.strip()
    if os.environ.get("FETIN_CHAVE"):
        return os.environ["FETIN_CHAVE"].strip()
    if ARQUIVO_CHAVE.exists():
        return ARQUIVO_CHAVE.read_text().strip()
    sys.exit(
        "Nenhuma chave encontrada. Passe --chave, defina FETIN_CHAVE "
        f"ou grave a chave em {ARQUIVO_CHAVE}"
    )


def main():
    p = argparse.ArgumentParser(description="Leitor facial da porta (Raspberry Pi)")
    p.add_argument("--api", required=True, help="ex: http://192.168.66.57:5000/api")
    p.add_argument("--chave", help="X-Device-Key (ou use ~/.fetin_chave)")
    p.add_argument("--camera", choices=["csi", "usb"], default="csi")
    p.add_argument("--uma-vez", action="store_true", help="captura só uma vez e sai")
    args = p.parse_args()

    chave = carregar_chave(args.chave)

    # Falha cedo e com mensagem clara se o servidor não estiver acessível -
    # é de longe o erro mais comum (IP mudou, firewall, wi-fi diferente).
    try:
        requests.get(f"{args.api}/health", timeout=5).raise_for_status()
    except Exception as e:
        sys.exit(f"Não consegui falar com o servidor em {args.api}\n  {e}")
    print(f"Servidor OK em {args.api}")

    camera = abrir_camera(args.camera)
    leds = Sinalizador()
    print("Leitor ativo. Ctrl+C pra parar.\n")

    try:
        while True:
            try:
                imagem = camera.capturar()
                r = reconhecer(args.api, chave, imagem)
            except requests.RequestException as e:
                # Rede caiu / servidor reiniciou: não é motivo pra derrubar
                # o leitor da porta. Avisa e tenta de novo no próximo laço.
                print(f"[rede] {e}")
                time.sleep(INTERVALO * 2)
                continue

            liberado = r.get("liberado")
            nome = r.get("nome") or "-"
            marca = time.strftime("%H:%M:%S")
            estado = "LIBERADO" if liberado else "  negado"
            print(f"{marca}  {estado}  {nome:<32} {r.get('motivo')}")

            leds.sinalizar(bool(liberado))

            if args.uma_vez:
                sys.exit(0 if liberado else 1)

            time.sleep(PAUSA_APOS_LIBERAR if liberado else INTERVALO)
    except KeyboardInterrupt:
        print("\nEncerrando.")
    finally:
        camera.fechar()


if __name__ == "__main__":
    main()
