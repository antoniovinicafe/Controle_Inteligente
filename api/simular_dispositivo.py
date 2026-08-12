"""
Simula o leitor facial da porta (a Raspberry Pi) a partir do PC.

Serve pra duas coisas:
  1. testar o /api/faces/recognize agora, com uma foto de verdade,
     sem precisar do hardware;
  2. é praticamente o código que vai rodar no Pi - lá muda só a
     origem da imagem (câmera em vez de arquivo) e o laço infinito.

Uso:
    python simular_dispositivo.py --chave <CHAVE> --foto caminho/da/foto.jpg
    python simular_dispositivo.py --chave <CHAVE> --webcam

A chave é a que apareceu uma única vez no cadastro do dispositivo
(POST /api/dispositivos). Se perdeu, gere outra em
POST /api/dispositivos/<id>/chave.
"""

import argparse
import sys

import requests

API_PADRAO = "http://127.0.0.1:5000/api"


def capturar_da_webcam() -> bytes:
    """Tira uma foto da webcam e devolve os bytes do JPEG."""
    import cv2

    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        sys.exit("Não consegui abrir a webcam.")
    print("Olhe pra câmera... capturando em 3 quadros.")
    for _ in range(3):  # descarta os primeiros, costumam vir escuros
        ok, frame = cam.read()
    cam.release()
    if not ok:
        sys.exit("Falha ao capturar imagem da webcam.")
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        sys.exit("Falha ao codificar a imagem.")
    return buf.tobytes()


def reconhecer(api: str, chave: str, imagem: bytes) -> dict:
    resposta = requests.post(
        f"{api}/faces/recognize",
        headers={"X-Device-Key": chave},
        files={"foto": ("captura.jpg", imagem, "image/jpeg")},
        timeout=60,  # DeepFace não é rápido na primeira chamada
    )
    resposta.raise_for_status()
    return resposta.json()


def main():
    p = argparse.ArgumentParser(description="Simula o leitor facial da porta")
    p.add_argument("--chave", required=True, help="X-Device-Key do dispositivo")
    p.add_argument("--foto", help="caminho de uma imagem")
    p.add_argument("--webcam", action="store_true", help="captura da webcam")
    p.add_argument("--api", default=API_PADRAO, help=f"padrão: {API_PADRAO}")
    args = p.parse_args()

    if args.webcam:
        imagem = capturar_da_webcam()
    elif args.foto:
        with open(args.foto, "rb") as f:
            imagem = f.read()
    else:
        p.error("informe --foto ou --webcam")

    resultado = reconhecer(args.api, args.chave, imagem)

    # É isto que o Pi vai usar pra acender o LED verde/vermelho ou
    # acionar a fechadura.
    liberado = resultado.get("liberado")
    print()
    print("=" * 46)
    print(" ACESSO LIBERADO" if liberado else " ACESSO NEGADO")
    print("=" * 46)
    if resultado.get("nome"):
        print(f" Pessoa : {resultado['nome']}")
    print(f" Motivo : {resultado.get('motivo')}")
    print()
    sys.exit(0 if liberado else 1)


if __name__ == "__main__":
    main()
