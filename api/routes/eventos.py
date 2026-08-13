from flask import Blueprint, request, jsonify, g

from utils.auth_middleware import login_required, require_role
from utils.db import get_conn, put_conn

bp = Blueprint("eventos", __name__, url_prefix="/api/eventos")


def _dono_do_evento_ou_admin(cur, evento_id):
    cur.execute("select * from eventos where id = %s", (evento_id,))
    evento = cur.fetchone()
    if not evento:
        return None, False
    return evento, (evento["criador_id"] == g.user_id or g.user_role == "admin")


# ------------------------------------------------------------
# CRUD de evento
# ------------------------------------------------------------
@bp.route("", methods=["POST"])
@login_required
@require_role("professor", "admin")
def criar_evento():
    body = request.get_json(force=True)
    campos_obrigatorios = ["titulo", "data_inicio", "data_fim"]
    faltando = [c for c in campos_obrigatorios if not body.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios faltando: {', '.join(faltando)}"}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into eventos (titulo, descricao, local, criador_id, data_inicio, data_fim, capacidade)
                values (%s, %s, %s, %s, %s, %s, %s)
                returning *
                """,
                (
                    body["titulo"],
                    body.get("descricao"),
                    body.get("local"),
                    g.user_id,
                    body["data_inicio"],
                    body["data_fim"],
                    body.get("capacidade"),
                ),
            )
            evento = cur.fetchone()
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify(evento), 201


@bp.route("", methods=["GET"])
@login_required
def listar_eventos():
    """Professor/admin vê os eventos que criou. Aluno vê os eventos em que foi convidado."""
    # Agenda: o que ainda vai acontecer vem primeiro, do mais próximo pro
    # mais distante; o que já passou fica embaixo, do mais recente pro mais
    # antigo. (Antes era `data_inicio desc` puro, o que jogava a aula do mês
    # que vem pro topo e enterrava a de amanhã.)
    ORDEM = """
        order by
            (e.data_fim < now()),
            case when e.data_fim >= now() then e.data_inicio end asc,
            e.data_inicio desc
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if g.user_role in ("professor", "admin"):
                cur.execute(
                    f"""
                    select e.*,
                        (select count(*) from evento_participantes ep where ep.evento_id = e.id) as total_participantes,
                        (select count(*) from evento_participantes ep where ep.evento_id = e.id and ep.status = 'liberado') as total_liberados
                    from eventos e
                    where e.criador_id = %s
                    {ORDEM}
                    """,
                    (g.user_id,),
                )
            else:
                cur.execute(
                    f"""
                    select e.*, ep.status as meu_status
                    from eventos e
                    join evento_participantes ep on ep.evento_id = e.id
                    where ep.usuario_id = %s
                    {ORDEM}
                    """,
                    (g.user_id,),
                )
            eventos = cur.fetchall()
    finally:
        put_conn(conn)

    return jsonify(eventos)


@bp.route("/<int:evento_id>", methods=["GET"])
@login_required
def detalhe_evento(evento_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("select * from eventos where id = %s", (evento_id,))
            evento = cur.fetchone()
    finally:
        put_conn(conn)

    if not evento:
        return jsonify({"erro": "Evento não encontrado"}), 404
    return jsonify(evento)


@bp.route("/<int:evento_id>", methods=["PATCH"])
@login_required
def editar_evento(evento_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            evento, autorizado = _dono_do_evento_ou_admin(cur, evento_id)
            if not evento:
                return jsonify({"erro": "Evento não encontrado"}), 404
            if not autorizado:
                return jsonify({"erro": "Sem permissão"}), 403

            body = request.get_json(force=True)
            campos = ["titulo", "descricao", "local", "data_inicio", "data_fim", "capacidade", "status"]
            atualizacoes = {c: body[c] for c in campos if c in body}
            if not atualizacoes:
                return jsonify({"erro": "Nada para atualizar"}), 400

            set_clause = ", ".join(f"{c} = %s" for c in atualizacoes)
            cur.execute(
                f"update eventos set {set_clause} where id = %s returning *",
                (*atualizacoes.values(), evento_id),
            )
            evento_atualizado = cur.fetchone()
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify(evento_atualizado)


@bp.route("/<int:evento_id>", methods=["DELETE"])
@login_required
def excluir_evento(evento_id):
    """
    Exclusão de verdade (apaga a linha, cascade em evento_participantes).
    Só permitida se não houver nenhum access_log - se já teve gente
    liberada (facial ou manual), o evento fica preservado pra auditoria;
    use PATCH .../status = 'cancelado' nesse caso.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            evento, autorizado = _dono_do_evento_ou_admin(cur, evento_id)
            if not evento:
                return jsonify({"erro": "Evento não encontrado"}), 404
            if not autorizado:
                return jsonify({"erro": "Sem permissão"}), 403

            cur.execute(
                "select count(*) as total from access_logs where evento_id = %s",
                (evento_id,),
            )
            if cur.fetchone()["total"] > 0:
                return jsonify({
                    "erro": "Esse evento já tem acessos registrados - não pode ser excluído. Cancele em vez de excluir."
                }), 409

            cur.execute("delete from eventos where id = %s", (evento_id,))
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify({"ok": True})


# ------------------------------------------------------------
# Participantes
# ------------------------------------------------------------
@bp.route("/<int:evento_id>/participantes", methods=["POST"])
@login_required
def convidar_participantes(evento_id):
    """
    Body aceita duas formas (pode combinar as duas no mesmo request):
      { "usuario_ids": ["uuid1", "uuid2"] }   -> convite manual
      { "turma_ids": [1, 2] }                 -> convida a turma inteira
    """
    body = request.get_json(force=True)
    usuario_ids = body.get("usuario_ids", [])
    turma_ids = body.get("turma_ids", [])

    if not usuario_ids and not turma_ids:
        return jsonify({"erro": "Informe usuario_ids e/ou turma_ids"}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            evento, autorizado = _dono_do_evento_ou_admin(cur, evento_id)
            if not evento:
                return jsonify({"erro": "Evento não encontrado"}), 404
            if not autorizado:
                return jsonify({"erro": "Sem permissão"}), 403

            total_convidados = 0

            for uid in usuario_ids:
                cur.execute(
                    """
                    insert into evento_participantes (evento_id, usuario_id, origem)
                    values (%s, %s, 'manual')
                    on conflict (evento_id, usuario_id) do nothing
                    """,
                    (evento_id, uid),
                )
                total_convidados += cur.rowcount

            for turma_id in turma_ids:
                cur.execute(
                    """
                    insert into evento_participantes (evento_id, usuario_id, origem, turma_id)
                    select %s, ta.aluno_id, 'turma', %s
                    from turma_alunos ta
                    where ta.turma_id = %s
                    on conflict (evento_id, usuario_id) do nothing
                    """,
                    (evento_id, turma_id, turma_id),
                )
                total_convidados += cur.rowcount

            # Capacidade é opcional, mas quando o professor define uma ela
            # precisa valer - antes o campo era só decorativo. Contamos o
            # total já com os inserts feitos e desfazemos tudo se estourar,
            # em vez de aceitar um convite pela metade.
            capacidade = evento["capacidade"]
            if capacidade is not None:
                cur.execute(
                    "select count(*) as n from evento_participantes where evento_id = %s",
                    (evento_id,),
                )
                total_final = cur.fetchone()["n"]
                if total_final > capacidade:
                    conn.rollback()
                    ja_tinha = total_final - total_convidados
                    vagas = capacidade - ja_tinha
                    if vagas <= 0:
                        detalhe = "o evento já está lotado"
                    else:
                        detalhe = f"só cabem mais {vagas}"
                    return jsonify({
                        "erro": f"Capacidade do evento é {capacidade} e já há "
                                f"{ja_tinha} participante(s): {detalhe}. "
                                f"Você tentou adicionar {total_convidados}."
                    }), 409

        conn.commit()
    finally:
        put_conn(conn)

    return jsonify({"ok": True, "total_convidados": total_convidados})


@bp.route("/<int:evento_id>/participantes", methods=["GET"])
@login_required
def listar_participantes(evento_id):
    """
    A lista de presença da aula.

    Cada linha traz também a primeira e a última vez que a porta liberou
    aquela pessoa nesta aula. É o mais perto de "permanência" que dá pra
    afirmar sem inventar hardware: o sistema sabe quando viu, não quando a
    pessoa saiu. Quem entra e não passa mais na frente da câmera tem uma
    leitura só — o professor vê "entrou 19:05" e nada além, que é
    exatamente o que se sabe.

    Sai tudo do access_logs, que já registrava cada leitura. Nenhuma tabela
    nova, nenhum fluxo novo pra ninguém aprender.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select ep.id, ep.status, ep.origem, ep.liberado_em,
                       p.id as usuario_id, p.nome, p.matricula,
                       -- sem rosto cadastrado o Raspberry Pi nunca reconhece
                       -- essa pessoa: o professor precisa saber de antemão
                       -- quem vai depender de liberação manual.
                       exists (select 1 from faces f where f.usuario_id = p.id) as tem_rosto,
                       -- Primeira e última vez que a porta liberou esta
                       -- pessoa nesta aula. Sai do access_logs, que já
                       -- guardava tudo isso: nenhuma tabela nova, nenhum
                       -- fluxo novo.
                       leituras.primeira_leitura,
                       leituras.ultima_leitura,
                       leituras.total as leituras
                from evento_participantes ep
                join profiles p on p.id = ep.usuario_id
                left join lateral (
                    select min(al.criado_em) as primeira_leitura,
                           max(al.criado_em) as ultima_leitura,
                           count(*) as total
                    from access_logs al
                    where al.evento_id = ep.evento_id
                      and al.usuario_id = ep.usuario_id
                      and al.status = 'liberado'
                ) leituras on true
                where ep.evento_id = %s
                order by p.nome
                """,
                (evento_id,),
            )
            participantes = cur.fetchall()
    finally:
        put_conn(conn)

    return jsonify(participantes)


@bp.route("/<int:evento_id>/participantes/<uuid:usuario_id>", methods=["DELETE"])
@login_required
def remover_participante(evento_id, usuario_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            evento, autorizado = _dono_do_evento_ou_admin(cur, evento_id)
            if not evento:
                return jsonify({"erro": "Evento não encontrado"}), 404
            if not autorizado:
                return jsonify({"erro": "Sem permissão"}), 403

            cur.execute(
                "delete from evento_participantes where evento_id = %s and usuario_id = %s",
                (evento_id, str(usuario_id)),
            )
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify({"ok": True})


# ------------------------------------------------------------
# Liberação manual (fallback pro reconhecimento facial)
# ------------------------------------------------------------
@bp.route("/<int:evento_id>/participantes/<uuid:usuario_id>/liberar", methods=["POST"])
@login_required
def liberar_manual(evento_id, usuario_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            evento, autorizado = _dono_do_evento_ou_admin(cur, evento_id)
            if not evento:
                return jsonify({"erro": "Evento não encontrado"}), 404
            if not autorizado:
                return jsonify({"erro": "Sem permissão"}), 403

            cur.execute(
                """
                update evento_participantes
                set status = 'liberado', liberado_em = now()
                where evento_id = %s and usuario_id = %s
                returning *
                """,
                (evento_id, str(usuario_id)),
            )
            participante = cur.fetchone()
            if not participante:
                return jsonify({"erro": "Participante não está convidado para este evento"}), 404

            cur.execute(
                """
                insert into access_logs (evento_id, usuario_id, tipo, status, motivo)
                values (%s, %s, 'manual', 'liberado', %s)
                """,
                (evento_id, str(usuario_id), f"Liberado manualmente por {g.user_nome}"),
            )
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify(participante)


# ------------------------------------------------------------
# Logs de acesso do evento
# ------------------------------------------------------------
@bp.route("/<int:evento_id>/logs", methods=["GET"])
@login_required
def logs_do_evento(evento_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            evento, autorizado = _dono_do_evento_ou_admin(cur, evento_id)
            if not evento:
                return jsonify({"erro": "Evento não encontrado"}), 404
            if not autorizado:
                return jsonify({"erro": "Sem permissão"}), 403

            cur.execute(
                """
                select al.*, p.nome, p.matricula
                from access_logs al
                left join profiles p on p.id = al.usuario_id
                where al.evento_id = %s
                order by al.criado_em desc
                """,
                (evento_id,),
            )
            logs = cur.fetchall()
    finally:
        put_conn(conn)

    return jsonify(logs)
