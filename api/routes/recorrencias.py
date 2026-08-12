"""
Regra de aula recorrente ("toda terça e quinta, 10h-12h, de 01/09 até
15/12", ligada a uma turma). Criar uma recorrência gera, de uma vez, um
evento de verdade pra cada ocorrência que bate com a regra - cada um já
convidando a turma inteira. Depois de criado, cada evento é
independente (cancelar/editar um não mexe nos outros).
"""

from datetime import datetime, timedelta, time as dtime

from flask import Blueprint, request, jsonify, g

from utils.auth_middleware import login_required, require_role
from utils.db import get_conn, put_conn

bp = Blueprint("recorrencias", __name__, url_prefix="/api/recorrencias")


def expandir_ocorrencias(dias_semana, data_inicio, data_fim):
    """Datas em que a regra cai, do início ao fim, inclusive nas pontas.

    Estava embutida no meio do laço que grava no banco, o que a tornava
    impossível de testar sem um Postgres de pé. Separada, é uma função pura
    de calendário - e precisa ser testada porque o aplicativo faz a MESMA
    conta do lado dele (`contarOcorrencias` em app/lib/models/recorrencia.dart)
    pra prometer "vai criar 15 aulas" ANTES de enviar. Se as duas contas
    discordarem, o app mente pro professor sobre o que o botão vai fazer.

    `dias_semana` usa 1=segunda .. 7=domingo, que é exatamente o que
    `date.isoweekday()` devolve no Python e `DateTime.weekday` no Dart - é
    essa coincidência que deixa os dois lados comparáveis.
    """
    datas = []
    dia = data_inicio
    while dia <= data_fim:
        if dia.isoweekday() in dias_semana:
            datas.append(dia)
        dia += timedelta(days=1)
    return datas


def _dono_da_recorrencia_ou_admin(cur, recorrencia_id):
    cur.execute("select * from recorrencias where id = %s", (recorrencia_id,))
    rec = cur.fetchone()
    if not rec:
        return None, False
    return rec, (rec["criador_id"] == g.user_id or g.user_role == "admin")


@bp.route("", methods=["POST"])
@login_required
@require_role("professor", "admin")
def criar_recorrencia():
    """
    Body: { turma_id, titulo, descricao?, local?, capacidade?,
            dias_semana: [1..7] (1=segunda .. 7=domingo),
            hora_inicio: "HH:MM", hora_fim: "HH:MM",
            data_inicio: "YYYY-MM-DD", data_fim: "YYYY-MM-DD" }
    """
    body = request.get_json(force=True)
    obrigatorios = ["turma_id", "titulo", "dias_semana", "hora_inicio", "hora_fim", "data_inicio", "data_fim"]
    faltando = [c for c in obrigatorios if not body.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios faltando: {', '.join(faltando)}"}), 400

    turma_id = body["turma_id"]
    dias_semana = body["dias_semana"]
    if not isinstance(dias_semana, list) or not all(isinstance(d, int) and 1 <= d <= 7 for d in dias_semana):
        return jsonify({"erro": "dias_semana deve ser uma lista de inteiros de 1 (segunda) a 7 (domingo)"}), 400

    try:
        hora_inicio = dtime.fromisoformat(body["hora_inicio"])
        hora_fim = dtime.fromisoformat(body["hora_fim"])
        data_inicio = datetime.strptime(body["data_inicio"], "%Y-%m-%d").date()
        data_fim = datetime.strptime(body["data_fim"], "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"erro": "Formato de data/hora inválido"}), 400

    if data_fim < data_inicio:
        return jsonify({"erro": "data_fim não pode ser antes de data_inicio"}), 400
    if hora_fim <= hora_inicio:
        return jsonify({"erro": "hora_fim precisa ser depois de hora_inicio"}), 400
    if (data_fim - data_inicio).days > 366:
        return jsonify({"erro": "Período máximo de 1 ano por recorrência"}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("select nome, professor_id from turmas where id = %s", (turma_id,))
            turma = cur.fetchone()
            if not turma:
                return jsonify({"erro": "Turma não encontrada"}), 404
            if turma["professor_id"] != g.user_id and g.user_role != "admin":
                return jsonify({"erro": "Sem permissão sobre essa turma"}), 403

            # Cada aula gerada convida a turma inteira, então uma capacidade
            # menor que a turma seria furada já na criação. Barra aqui, antes
            # de criar qualquer coisa - a mesma regra que o convite manual
            # aplica, pra não dar respostas diferentes pro mesmo problema.
            capacidade = body.get("capacidade")
            if capacidade is not None:
                cur.execute(
                    "select count(*) as n from turma_alunos where turma_id = %s",
                    (turma_id,),
                )
                total_alunos = cur.fetchone()["n"]
                if total_alunos > capacidade:
                    return jsonify({
                        "erro": f'A turma "{turma["nome"]}" tem {total_alunos} aluno(s), '
                                f"mais que a capacidade informada ({capacidade}). "
                                f"Aumente a capacidade ou deixe o campo em branco."
                    }), 409

            cur.execute(
                """
                insert into recorrencias
                    (turma_id, titulo, descricao, local, dias_semana, hora_inicio, hora_fim,
                     data_inicio, data_fim, capacidade, criador_id)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning id
                """,
                (
                    turma_id, body["titulo"], body.get("descricao"), body.get("local"),
                    dias_semana, hora_inicio, hora_fim, data_inicio, data_fim,
                    body.get("capacidade"), g.user_id,
                ),
            )
            recorrencia_id = cur.fetchone()["id"]

            cur.execute("select aluno_id from turma_alunos where turma_id = %s", (turma_id,))
            alunos = [row["aluno_id"] for row in cur.fetchall()]

            total_eventos = 0
            for dia in expandir_ocorrencias(dias_semana, data_inicio, data_fim):
                cur.execute(
                    """
                    insert into eventos
                        (titulo, descricao, local, criador_id, data_inicio, data_fim,
                         capacidade, recorrencia_id)
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    returning id
                    """,
                    (
                        body["titulo"], body.get("descricao"), body.get("local"), g.user_id,
                        datetime.combine(dia, hora_inicio),
                        datetime.combine(dia, hora_fim),
                        body.get("capacidade"), recorrencia_id,
                    ),
                )
                evento_id = cur.fetchone()["id"]
                for aluno_id in alunos:
                    cur.execute(
                        """
                        insert into evento_participantes (evento_id, usuario_id, origem, turma_id)
                        values (%s, %s, 'turma', %s)
                        on conflict (evento_id, usuario_id) do nothing
                        """,
                        (evento_id, aluno_id, turma_id),
                    )
                total_eventos += 1
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify({"id": recorrencia_id, "total_eventos": total_eventos}), 201


@bp.route("", methods=["GET"])
@login_required
def listar_recorrencias():
    """Lista as recorrências criadas pelo usuário (só professor/admin usa isso)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select * from recorrencias where criador_id = %s order by criado_em desc",
                (g.user_id,),
            )
            recorrencias = cur.fetchall()
    finally:
        put_conn(conn)
    return jsonify(recorrencias)


@bp.route("/<int:recorrencia_id>", methods=["DELETE"])
@login_required
def cancelar_recorrencia(recorrencia_id):
    """
    Cancela só as ocorrências que ainda não aconteceram (data_inicio no
    futuro) - as passadas ficam intactas, com o histórico de acesso
    preservado.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            rec, autorizado = _dono_da_recorrencia_ou_admin(cur, recorrencia_id)
            if not rec:
                return jsonify({"erro": "Recorrência não encontrada"}), 404
            if not autorizado:
                return jsonify({"erro": "Sem permissão"}), 403

            cur.execute(
                """
                update eventos set status = 'cancelado'
                where recorrencia_id = %s and data_inicio > now() and status != 'cancelado'
                returning id
                """,
                (recorrencia_id,),
            )
            canceladas = cur.fetchall()
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify({"ok": True, "eventos_cancelados": len(canceladas)})
