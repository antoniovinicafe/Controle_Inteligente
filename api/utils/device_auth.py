"""
Autenticação de DISPOSITIVO (a Raspberry Pi na porta da sala).

Um leitor facial não é uma pessoa: não faz login, não tem senha pra
digitar e não pode depender de um JWT que expira em 1h. Por isso ele
usa um caminho próprio, separado do `login_required`:

    X-Device-Key: <chave gerada no cadastro do dispositivo>

A chave só aparece em texto UMA vez, no momento do cadastro - no banco
fica só o hash (SHA-256). Se o professor perder, gera outra; ninguém
consegue ler a original de volta, nem quem tiver acesso ao banco.
"""

import hashlib
import secrets
from functools import wraps

import psycopg2
from flask import request, jsonify, g

from services import cache_local
from utils.db import get_conn, marcar_com_banco, marcar_sem_banco, put_conn, sem_banco


def gerar_chave() -> str:
    """Chave nova pra um dispositivo. 32 bytes em base64-url ≈ 43 chars."""
    return secrets.token_urlsafe(32)


def hash_chave(chave: str) -> str:
    """
    SHA-256 puro (sem salt) de propósito: diferente de senha de usuário,
    a chave é aleatória de 256 bits, então não há o que quebrar por
    força bruta ou rainbow table - e o hash precisa ser determinístico
    pra dar pra procurar por ele no banco em uma query.
    """
    return hashlib.sha256(chave.encode()).hexdigest()


def _da_copia(chave_hash: str):
    """
    O dispositivo pela cópia local. Devolve o registro, ou já a resposta
    HTTP de recusa (que quem chama reconhece por ser uma tupla).
    """
    copia = cache_local.carregar()
    if not copia:
        # Sem banco e sem cópia não há como saber se a chave presta. Recusar
        # é a única opção honesta - e o 503 diz que o problema é o servidor,
        # não a chave do leitor.
        return jsonify({"erro": "Servidor sem banco e sem cópia local"}), 503

    dispositivo = cache_local.dispositivo_por_hash(copia, chave_hash)
    if not dispositivo:
        return jsonify({"erro": "Chave de dispositivo inválida"}), 401
    if not dispositivo["ativo"]:
        return jsonify({"erro": "Dispositivo desativado"}), 403
    return dispositivo


def device_required(f):
    """
    Exige um X-Device-Key válido de um dispositivo ativo.
    Popula g.dispositivo_id, g.dispositivo_nome e g.dispositivo_local.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        chave = request.headers.get("X-Device-Key", "").strip()
        if not chave:
            return jsonify({"erro": "Dispositivo não identificado"}), 401

        chave_hash = hash_chave(chave)

        # Sem banco, o leitor é reconhecido pela cópia local. Ela guarda o
        # mesmo hash que o Postgres, então a chave continua valendo o que
        # valia - o que se perde é só o heartbeat, e saber que o leitor está
        # vivo importa muito menos do que a porta abrir.
        if sem_banco():
            dispositivo = _da_copia(chave_hash)
            if isinstance(dispositivo, tuple):
                return dispositivo
        else:
            conn = None
            try:
                conn = get_conn()
                with conn.cursor() as cur:
                    cur.execute(
                        "select id, nome, local, normaliza_local(local) as local_norm, "
                        "ativo from dispositivos where chave_hash = %s",
                        (chave_hash,),
                    )
                    dispositivo = cur.fetchone()

                    if not dispositivo:
                        return jsonify({"erro": "Chave de dispositivo inválida"}), 401
                    if not dispositivo["ativo"]:
                        return jsonify({"erro": "Dispositivo desativado"}), 403

                    # Serve de "heartbeat": dá pra ver na tela do professor
                    # se o leitor da sala ainda está vivo.
                    cur.execute(
                        "update dispositivos set ultimo_visto = now() where id = %s",
                        (dispositivo["id"],),
                    )
                conn.commit()
                marcar_com_banco()
            except psycopg2.Error:
                # Banco fora de alcance. Não é erro do leitor nem motivo pra
                # 500: é o caso pro qual a cópia local existe.
                marcar_sem_banco()
                dispositivo = _da_copia(chave_hash)
                if isinstance(dispositivo, tuple):
                    return dispositivo
            finally:
                if conn is not None:
                    put_conn(conn)

        g.dispositivo_id = dispositivo["id"]
        g.dispositivo_nome = dispositivo["nome"]
        g.dispositivo_local = dispositivo["local"]
        # A decisão offline compara sala já normalizada; online quem
        # normaliza é o Postgres, então este campo pode não existir.
        g.dispositivo_local_norm = dispositivo.get("local_norm")

        return f(*args, **kwargs)

    return wrapper
