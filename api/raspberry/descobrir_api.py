"""Descobre o endereço do servidor Fetin sem depender de IP fixo.

POR QUE ISTO EXISTE
O IP da máquina que roda o Flask muda sozinho — trocar de Wi-Fi, o roteador
renovar o DHCP. Num único dia de trabalho ele mudou cinco vezes. O aplicativo
resolveu isso com uma tela de Ajustes; a porta não tinha equivalente: o
endereço vinha fixo na linha de comando do serviço systemd, e consertar
significava achar o IP da Raspberry, dar SSH, editar o serviço e reiniciar —
tudo isso num local com rede que ninguém controla e com a Raspberry sem
teclado nem monitor.

A ORDEM DE BUSCA (a primeira que funcionar vence)

  1. --api na linha de comando   continua tendo prioridade absoluta, então
                                 nada que já funciona muda de comportamento
  2. variável FETIN_API          prática no EnvironmentFile do systemd
  3. ~/.fetin/api                arquivo de uma linha, fácil de editar por SSH
  4. varredura da rede local     último recurso: procura quem responde
                                 /api/health na mesma faixa da Raspberry

O endereço que funcionar é gravado em ~/.fetin/api. Então a varredura custa
alguns segundos UMA vez; nos boots seguintes o arquivo é lido direto. E se o
IP mudar de novo, o gravado falha na verificação e a varredura roda outra vez
sozinha — sem ninguém precisar intervir.

O QUE JÁ FOI TESTADO (12/08/2026, do PC, com o Flask no ar)
  normalizar()  aceita "IP", "IP:porta" e a URL inteira, com ou sem /api
  responde()    distingue servidor vivo de porta morta
  _ip_local()   devolve o IP da interface em uso
  varredura     254 endereços em 2,6s, achou o servidor certo

O que ainda NÃO foi exercitado é rodar isto na própria Raspberry — em
particular o filtro que exclui o IP local dos alvos, que aqui não pôde ser
verificado porque nesta máquina o servidor É o IP local. Na Pi o servidor
está sempre em outra máquina, então a exclusão é o comportamento correto.
Ao voltar com a Pi: `python3 descobrir_api.py` deve imprimir o endereço.
"""

import ipaddress
import os
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

PORTA_PADRAO = 5000
ARQUIVO_CACHE = Path.home() / ".fetin" / "api"

# Curto de propósito: são dezenas de endereços em paralelo numa rede local,
# onde quem existe responde em milissegundos e quem não existe não responde.
TIMEOUT_VARREDURA = 0.6
TIMEOUT_VERIFICACAO = 4.0


def normalizar(bruto):
    """Aceita "192.168.0.10", "192.168.0.10:5000" ou a URL inteira."""
    url = (bruto or "").strip().rstrip("/")
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    if ":" not in url.split("//", 1)[1]:
        url = f"{url}:{PORTA_PADRAO}"
    if not url.endswith("/api"):
        url = f"{url}/api"
    return url


def responde(api, timeout=TIMEOUT_VERIFICACAO):
    """True se há um servidor Fetin de pé nesse endereço."""
    try:
        r = requests.get(f"{api}/health", timeout=timeout)
        return r.ok and r.json().get("status") == "ok"
    except Exception:
        return False


def _ip_local():
    """IP da Raspberry na rede atual.

    O truque do socket UDP não envia pacote nenhum: só faz o sistema escolher
    qual interface usaria pra sair, que é exatamente a que interessa. Bem mais
    confiável que gethostname(), que em Linux costuma devolver 127.0.1.1.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def varrer(porta=PORTA_PADRAO, ao_encontrar=None):
    """Procura o servidor na mesma faixa /24 da Raspberry."""
    meu_ip = _ip_local()
    if not meu_ip:
        return ""

    rede = ipaddress.ip_network(f"{meu_ip}/24", strict=False)
    alvos = [str(ip) for ip in rede.hosts() if str(ip) != meu_ip]

    def testar(ip):
        api = f"http://{ip}:{porta}/api"
        return api if responde(api, timeout=TIMEOUT_VARREDURA) else None

    with ThreadPoolExecutor(max_workers=64) as pool:
        futuros = {pool.submit(testar, ip): ip for ip in alvos}
        for fut in as_completed(futuros):
            achado = fut.result()
            if achado:
                # Cancela o resto: achar um servidor já basta.
                for f in futuros:
                    f.cancel()
                if ao_encontrar:
                    ao_encontrar(achado)
                return achado
    return ""


def _ler_cache():
    try:
        return normalizar(ARQUIVO_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return ""


def gravar_cache(api):
    try:
        ARQUIVO_CACHE.parent.mkdir(parents=True, exist_ok=True)
        ARQUIVO_CACHE.write_text(api + "\n", encoding="utf-8")
    except Exception:
        pass  # cache é conveniência, não pode derrubar o programa


def resolver(api_explicito=None, avisar=print):
    """Devolve o endereço do servidor, ou "" se não achou nenhum.

    `api_explicito` é o --api da linha de comando: se vier, vence tudo e nem
    é verificado, pra não mudar o comportamento de quem já passa o endereço.
    """
    if api_explicito:
        return normalizar(api_explicito)

    do_ambiente = normalizar(os.environ.get("FETIN_API", ""))
    if do_ambiente:
        avisar(f"Servidor pelo FETIN_API: {do_ambiente}")
        return do_ambiente

    do_cache = _ler_cache()
    if do_cache:
        avisar(f"Testando o último endereço conhecido: {do_cache}")
        if responde(do_cache):
            return do_cache
        avisar("Não respondeu — o IP deve ter mudado. Varrendo a rede...")
    else:
        avisar("Nenhum endereço salvo. Varrendo a rede...")

    achado = varrer()
    if achado:
        gravar_cache(achado)
        avisar(f"Servidor encontrado em {achado} (salvo em {ARQUIVO_CACHE})")
        return achado

    avisar("Nenhum servidor Fetin encontrado nesta rede.")
    return ""


if __name__ == "__main__":
    # Teste manual: python3 descobrir_api.py
    encontrado = resolver()
    if not encontrado:
        sys.exit(1)
    print(encontrado)
