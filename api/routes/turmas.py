from flask import Blueprint, request, jsonify, g

from utils.auth_middleware import login_required, require_role
from utils.curso import curso_do_email
from utils.db import get_conn, put_conn

bp = Blueprint("turmas", __name__, url_prefix="/api/turmas")


@bp.route("", methods=["POST"])
@login_required
@require_role("professor", "admin")
def criar_turma():
    body = request.get_json(force=True)
    nome = body.get("nome")
    if not nome:
        return jsonify({"erro": "nome é obrigatório"}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into turmas (nome, professor_id) values (%s, %s) returning *",
                (nome, g.user_id),
            )
            turma = cur.fetchone()
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify(turma), 201


@bp.route("", methods=["GET"])
@login_required
def listar_turmas():
    """Professor/admin vê as turmas que criou. Aluno vê as turmas em que está."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if g.user_role in ("professor", "admin"):
                cur.execute(
                    """
                    select t.*, count(ta.aluno_id) as total_alunos
                    from turmas t
                    left join turma_alunos ta on ta.turma_id = t.id
                    where t.professor_id = %s
                    group by t.id
                    order by t.criado_em desc
                    """,
                    (g.user_id,),
                )
            else:
                cur.execute(
                    """
                    select t.*
                    from turmas t
                    join turma_alunos ta on ta.turma_id = t.id
                    where ta.aluno_id = %s
                    order by t.criado_em desc
                    """,
                    (g.user_id,),
                )
            turmas = cur.fetchall()
    finally:
        put_conn(conn)

    return jsonify(turmas)


def _dono_da_turma_ou_admin(cur, turma_id):
    cur.execute("select professor_id from turmas where id = %s", (turma_id,))
    turma = cur.fetchone()
    if not turma:
        return None, False
    return turma, (turma["professor_id"] == g.user_id or g.user_role == "admin")


@bp.route("/<int:turma_id>/alunos", methods=["POST"])
@login_required
@require_role("professor", "admin")
def adicionar_alunos(turma_id):
    """Body: { "aluno_ids": ["uuid1", "uuid2", ...] }"""
    body = request.get_json(force=True)
    aluno_ids = body.get("aluno_ids", [])
    if not aluno_ids:
        return jsonify({"erro": "aluno_ids é obrigatório"}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            turma, autorizado = _dono_da_turma_ou_admin(cur, turma_id)
            if not turma:
                return jsonify({"erro": "Turma não encontrada"}), 404
            if not autorizado:
                return jsonify({"erro": "Você não tem permissão para editar esta turma"}), 403

            for aluno_id in aluno_ids:
                cur.execute(
                    """
                    insert into turma_alunos (turma_id, aluno_id)
                    values (%s, %s)
                    on conflict do nothing
                    """,
                    (turma_id, aluno_id),
                )

            # Aluno que entra na turma já é convidado automaticamente pras
            # aulas de recorrência dessa turma que ainda não aconteceram -
            # as que já passaram (ou já foram canceladas) ficam como estão.
            cur.execute(
                """
                select e.id from eventos e
                join recorrencias r on r.id = e.recorrencia_id
                where r.turma_id = %s and e.data_inicio > now() and e.status != 'cancelado'
                """,
                (turma_id,),
            )
            eventos_futuros = [row["id"] for row in cur.fetchall()]
            lotados = 0
            for evento_id in eventos_futuros:
                # Entrar na turma é cadastro e não tem limite; a aula é que
                # acontece numa sala com lugares contados. Se o novo aluno
                # não couber, ele entra na turma mesmo assim e só fica de
                # fora dessa ocorrência - nunca estourando a capacidade.
                cur.execute(
                    """
                    select e.capacidade,
                           (select count(*) from evento_participantes ep
                             where ep.evento_id = e.id) as ocupados
                    from eventos e where e.id = %s
                    """,
                    (evento_id,),
                )
                vaga = cur.fetchone()
                if vaga["capacidade"] is not None and \
                        vaga["ocupados"] + len(aluno_ids) > vaga["capacidade"]:
                    lotados += 1
                    continue

                for aluno_id in aluno_ids:
                    cur.execute(
                        """
                        insert into evento_participantes (evento_id, usuario_id, origem, turma_id)
                        values (%s, %s, 'turma', %s)
                        on conflict (evento_id, usuario_id) do nothing
                        """,
                        (evento_id, aluno_id, turma_id),
                    )
        conn.commit()
    finally:
        put_conn(conn)

    resposta = {"ok": True, "adicionados": len(aluno_ids)}
    if lotados:
        resposta["aulas_lotadas"] = lotados
        resposta["aviso"] = (
            f"{lotados} aula(s) futura(s) já estão na capacidade máxima - "
            f"o(s) aluno(s) entrou(aram) na turma, mas não foi(ram) convidado(s) pra essa(s)."
        )
    return jsonify(resposta)


@bp.route("/<int:turma_id>/alunos/<uuid:aluno_id>", methods=["DELETE"])
@login_required
@require_role("professor", "admin")
def remover_aluno(turma_id, aluno_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            turma, autorizado = _dono_da_turma_ou_admin(cur, turma_id)
            if not turma:
                return jsonify({"erro": "Turma não encontrada"}), 404
            if not autorizado:
                return jsonify({"erro": "Você não tem permissão para editar esta turma"}), 403

            cur.execute(
                "delete from turma_alunos where turma_id = %s and aluno_id = %s",
                (turma_id, str(aluno_id)),
            )
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify({"ok": True})


@bp.route("/<int:turma_id>/frequencia", methods=["GET"])
@login_required
@require_role("professor", "admin")
def frequencia_da_turma(turma_id):
    """
    Presença de cada aluno nas aulas já encerradas dessa turma.

    Parte de `turma_alunos` com LEFT JOIN pra que aluno recém-adicionado
    apareça com 0 de 0 em vez de sumir da lista. Aula cancelada não conta
    contra ninguém, e aula que ainda não terminou também não.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            turma, autorizado = _dono_da_turma_ou_admin(cur, turma_id)
            if not turma:
                return jsonify({"erro": "Turma não encontrada"}), 404
            if not autorizado:
                return jsonify({"erro": "Sem permissão"}), 403

            cur.execute(
                """
                select p.id, p.nome, p.matricula, u.email,
                       count(e.id) as total,
                       count(e.id) filter (where ep.status = 'liberado') as presencas
                from turma_alunos ta
                join profiles p on p.id = ta.aluno_id
                join auth.users u on u.id = p.id
                left join evento_participantes ep
                       on ep.usuario_id = ta.aluno_id and ep.turma_id = ta.turma_id
                left join eventos e
                       on e.id = ep.evento_id
                      and e.data_fim < now()
                      and e.status != 'cancelado'
                where ta.turma_id = %s
                group by p.id, p.nome, p.matricula, u.email
                order by p.nome
                """,
                (turma_id,),
            )
            alunos = cur.fetchall()
    finally:
        put_conn(conn)

    return jsonify([
        {
            **{k: v for k, v in a.items() if k != "email"},   # e-mail não sai daqui
            "curso": curso_do_email(a["email"]),
            "faltas": a["total"] - a["presencas"],
            "percentual": round(a["presencas"] * 100 / a["total"]) if a["total"] else None,
        }
        for a in alunos
    ])


@bp.route("/<int:turma_id>/alunos", methods=["GET"])
@login_required
def listar_alunos_da_turma(turma_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select p.id, p.nome, p.matricula
                from turma_alunos ta
                join profiles p on p.id = ta.aluno_id
                where ta.turma_id = %s
                order by p.nome
                """,
                (turma_id,),
            )
            alunos = cur.fetchall()
    finally:
        put_conn(conn)

    return jsonify(alunos)
