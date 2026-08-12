"""
Cadastro dos leitores faciais (Raspberry Pi) que ficam na porta das salas.

Quem gerencia é professor/admin. A chave de acesso do dispositivo é
mostrada UMA única vez, na resposta do cadastro - depois disso só existe
o hash no banco. Perdeu, gera outra.
"""

from flask import Blueprint, request, jsonify, g

from utils.auth_middleware import login_required, require_role
from utils.device_auth import gerar_chave, hash_chave
from utils.db import get_conn, put_conn

bp = Blueprint("dispositivos", __name__, url_prefix="/api/dispositivos")


@bp.route("", methods=["POST"])
@login_required
@require_role("professor", "admin")
def criar_dispositivo():
    """Body: { nome, local }. Devolve a chave em texto (única chance de vê-la)."""
    body = request.get_json(force=True)
    nome = (body.get("nome") or "").strip()
    local = (body.get("local") or "").strip()
    if not nome or not local:
        return jsonify({"erro": "Informe nome e local do dispositivo"}), 400

    chave = gerar_chave()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into dispositivos (nome, local, chave_hash, criado_por)
                values (%s, %s, %s, %s)
                returning id, nome, local, ativo, criado_em
                """,
                (nome, local, hash_chave(chave), g.user_id),
            )
            dispositivo = cur.fetchone()
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify({
        **dispositivo,
        "chave": chave,
        "aviso": "Guarde esta chave agora - ela não será mostrada de novo.",
    }), 201


@bp.route("", methods=["GET"])
@login_required
@require_role("professor", "admin")
def listar_dispositivos():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, nome, local, ativo, ultimo_visto, criado_em
                from dispositivos
                order by nome
                """
            )
            dispositivos = cur.fetchall()
    finally:
        put_conn(conn)
    return jsonify(dispositivos)


@bp.route("/<int:dispositivo_id>", methods=["PATCH"])
@login_required
@require_role("professor", "admin")
def atualizar_dispositivo(dispositivo_id):
    """Serve pra renomear, mudar de sala e principalmente ativar/desativar."""
    body = request.get_json(force=True)
    campos = {c: body[c] for c in ("nome", "local", "ativo") if c in body}
    if not campos:
        return jsonify({"erro": "Nada para atualizar"}), 400

    set_clause = ", ".join(f"{c} = %s" for c in campos)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""update dispositivos set {set_clause} where id = %s
                    returning id, nome, local, ativo, ultimo_visto, criado_em""",
                (*campos.values(), dispositivo_id),
            )
            dispositivo = cur.fetchone()
            if not dispositivo:
                return jsonify({"erro": "Dispositivo não encontrado"}), 404
        conn.commit()
    finally:
        put_conn(conn)
    return jsonify(dispositivo)


@bp.route("/<int:dispositivo_id>/chave", methods=["POST"])
@login_required
@require_role("professor", "admin")
def regerar_chave(dispositivo_id):
    """Invalida a chave antiga na hora e devolve uma nova."""
    chave = gerar_chave()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update dispositivos set chave_hash = %s where id = %s returning id, nome",
                (hash_chave(chave), dispositivo_id),
            )
            dispositivo = cur.fetchone()
            if not dispositivo:
                return jsonify({"erro": "Dispositivo não encontrado"}), 404
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify({
        **dispositivo,
        "chave": chave,
        "aviso": "A chave anterior deixou de funcionar. Atualize o dispositivo.",
    })


@bp.route("/<int:dispositivo_id>", methods=["DELETE"])
@login_required
@require_role("professor", "admin")
def remover_dispositivo(dispositivo_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "delete from dispositivos where id = %s returning id", (dispositivo_id,)
            )
            if not cur.fetchone():
                return jsonify({"erro": "Dispositivo não encontrado"}), 404
        conn.commit()
    finally:
        put_conn(conn)
    return jsonify({"ok": True})
