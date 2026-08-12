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

from flask import request, jsonify, g

from utils.db import get_conn, put_conn


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

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "select id, nome, local, ativo from dispositivos where chave_hash = %s",
                    (hash_chave(chave),),
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
        finally:
            put_conn(conn)

        g.dispositivo_id = dispositivo["id"]
        g.dispositivo_nome = dispositivo["nome"]
        g.dispositivo_local = dispositivo["local"]

        return f(*args, **kwargs)

    return wrapper
