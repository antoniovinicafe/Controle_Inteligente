from flask import Blueprint, request, jsonify, g

from utils.auth_middleware import login_required, require_role
from utils.db import get_conn, put_conn

bp = Blueprint("usuarios", __name__, url_prefix="/api/usuarios")


@bp.route("/me", methods=["GET"])
@login_required
def meu_perfil():
    """Retorna o perfil do usuário logado (usado pelo app pra saber o papel/role)."""
    return jsonify({
        "id": g.user_id,
        "nome": g.user_nome,
        "matricula": g.user_matricula,
        "role": g.user_role,
    })


# Uma aula só entra no cálculo depois de terminar, e aula cancelada não
# conta contra ninguém - senão o professor cancelar a aula derrubaria a
# frequência de quem nem teve a chance de comparecer.
_AULAS_QUE_CONTAM = "e.data_fim < now() and e.status != 'cancelado'"


@bp.route("/me/frequencia", methods=["GET"])
@login_required
def minha_frequencia():
    """Quantas das aulas já encerradas em que fui convidado eu realmente frequentei."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select count(*) as total,
                       count(*) filter (where ep.status = 'liberado') as presencas
                from evento_participantes ep
                join eventos e on e.id = ep.evento_id
                where ep.usuario_id = %s and {_AULAS_QUE_CONTAM}
                """,
                (g.user_id,),
            )
            r = cur.fetchone()
    finally:
        put_conn(conn)

    total = r["total"]
    presencas = r["presencas"]
    return jsonify({
        "total": total,
        "presencas": presencas,
        "faltas": total - presencas,
        # None (e não 0) quando ainda não houve aula: "0%" mentiria.
        "percentual": round(presencas * 100 / total) if total else None,
    })


@bp.route("/complete-cadastro", methods=["POST"])
@login_required(perfil_obrigatorio=False)
def completar_cadastro():
    """
    Chamado uma vez, logo após o primeiro login via Supabase Auth,
    pra criar a linha correspondente em `profiles` (nome, matrícula, role).
    """
    body = request.get_json(force=True)
    nome = body.get("nome")
    matricula = body.get("matricula")
    role = body.get("role", "aluno")

    if not nome:
        return jsonify({"erro": "nome é obrigatório"}), 400
    if role not in ("admin", "professor", "aluno"):
        return jsonify({"erro": "role inválido"}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into profiles (id, nome, matricula, role)
                values (%s, %s, %s, %s)
                on conflict (id) do update set nome = excluded.nome, matricula = excluded.matricula
                returning id, nome, matricula, role
                """,
                (g.user_id, nome, matricula, role),
            )
            profile = cur.fetchone()
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify(profile), 201


@bp.route("", methods=["GET"])
@login_required
@require_role("admin", "professor")
def listar_usuarios():
    """
    Lista usuários - usado nas telas de 'adicionar participante'
    e 'adicionar aluno na turma'. Aceita ?busca= e ?role=.
    """
    busca = request.args.get("busca", "").strip()
    role = request.args.get("role")

    query = "select id, nome, matricula, role from profiles where 1=1"
    params = []
    if busca:
        query += " and (nome ilike %s or matricula ilike %s)"
        params += [f"%{busca}%", f"%{busca}%"]
    if role:
        query += " and role = %s"
        params.append(role)
    query += " order by nome limit 50"

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            usuarios = cur.fetchall()
    finally:
        put_conn(conn)

    return jsonify(usuarios)


@bp.route("/<uuid:usuario_id>/role", methods=["PATCH"])
@login_required
@require_role("admin")
def alterar_role(usuario_id):
    """Só admin pode promover/rebaixar papel de um usuário."""
    body = request.get_json(force=True)
    role = body.get("role")
    if role not in ("admin", "professor", "aluno"):
        return jsonify({"erro": "role inválido"}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update profiles set role = %s where id = %s returning id, nome, role",
                (role, str(usuario_id)),
            )
            profile = cur.fetchone()
        conn.commit()
    finally:
        put_conn(conn)

    if not profile:
        return jsonify({"erro": "Usuário não encontrado"}), 404
    return jsonify(profile)
