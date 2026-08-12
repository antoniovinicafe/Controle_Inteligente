"""
Cadastra o SEU rosto usando a câmera do próprio Pi.

No uso normal quem faz isso é o app (tela "Cadastrar meu rosto"). Este
script existe pra destravar o teste do leitor sem depender do celular:
sem nenhum rosto no banco, o /recognize só sabe responder "Rosto não
reconhecido" e não dá pra validar o resto da cadeia.

Vantagem de cadastrar pela câmera do Pi: o rosto entra no banco vindo
da MESMA lente, mesma lente/iluminação que vai ler na porta - é o
cenário mais favorável pro reconhecimento acertar.

Uso:
    python3 cadastrar_rosto.py --api http://192.168.66.57:5000/api \
        --email seu@email --senha suasenha

A senha só é usada pra pegar o token do Supabase, igual o app faz.
Nada é gravado em disco.
"""

import argparse
import getpass
import sys

import requests

SUPABASE_URL = "https://udslgrllcgsmlwktuweb.supabase.co"
SUPABASE_ANON = "sb_publishable_5WE15j_FkEOaTGNOff-SNw_VfElDcsG"


def login(email: str, senha: str) -> str:
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON},
        json={"email": email, "password": senha},
        timeout=20,
    )
    if not r.ok:
        sys.exit(f"Login falhou ({r.status_code}): {r.text}")
    return r.json()["access_token"]


def capturar() -> bytes:
    """Mesma captura do leitor_porta.py, mas uma foto só."""
    try:
        from picamera2 import Picamera2
    except ImportError:
        sys.exit("Instale a câmera: sudo apt install -y python3-picamera2")

    import io
    import time

    cam = Picamera2()
    cam.configure(cam.create_still_configuration(main={"size": (640, 480)}))
    cam.start()
    print("Olhe pra câmera. Foto em 3 segundos...")
    time.sleep(3)
    buf = io.BytesIO()
    cam.capture_file(buf, format="jpeg")
    cam.stop()
    return buf.getvalue()


def main():
    p = argparse.ArgumentParser(description="Cadastra seu rosto pela câmera do Pi")
    p.add_argument("--api", required=True, help="ex: http://192.168.66.57:5000/api")
    p.add_argument("--email", help="se omitir, use --token")
    p.add_argument("--senha", help="se omitir, pergunta sem exibir na tela")
    p.add_argument(
        "--token",
        help="access_token do Supabase já pronto, no lugar de email+senha. "
        "Útil pra rodar o cadastro remotamente sem deixar a senha no "
        "histórico do shell do Pi.",
    )
    args = p.parse_args()

    if args.token:
        token = args.token
    elif args.email:
        senha = args.senha or getpass.getpass("Senha: ")
        token = login(args.email, senha)
        print("Login OK.")
    else:
        p.error("informe --email (com --senha) ou --token")

    imagem = capturar()
    print(f"Foto capturada ({len(imagem) // 1024} KB). Enviando...")

    r = requests.post(
        f"{args.api}/faces",
        headers={"Authorization": f"Bearer {token}"},
        files={"foto": ("rosto.jpg", imagem, "image/jpeg")},
        timeout=120,  # primeira chamada carrega o Facenet512 no servidor
    )

    if r.status_code == 422:
        # Erro esperado e comum: rosto não detectado. Vale orientar em vez
        # de só cuspir o JSON.
        sys.exit(
            f"O servidor não achou um rosto na foto: {r.json().get('erro')}\n"
            "Tente de novo com mais luz, de frente e mais perto da câmera."
        )
    if not r.ok:
        sys.exit(f"Falhou ({r.status_code}): {r.text}")

    print("Rosto cadastrado com sucesso:", r.json())


if __name__ == "__main__":
    main()
