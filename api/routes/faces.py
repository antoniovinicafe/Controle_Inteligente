from flask import Blueprint, request, jsonify, g

from utils.auth_middleware import login_required
from utils.device_auth import device_required
from utils.db import get_conn, put_conn
from services.face_service import calcular_embedding, MODELO, RostoFalsoError

bp = Blueprint("faces", __name__, url_prefix="/api/faces")


@bp.route("", methods=["POST"])
@login_required
def cadastrar_rosto():
    """
    Recebe a foto via multipart/form-data (campo 'foto'), calcula o
    embedding e salva/atualiza o vetor do usuário logado.
    A imagem em si não é persistida em lugar nenhum.
    """
    if "foto" not in request.files:
        return jsonify({"erro": "Envie a imagem no campo 'foto' (multipart/form-data)"}), 400

    foto = request.files["foto"]
    imagem_bytes = foto.read()
    if not imagem_bytes:
        return jsonify({"erro": "Arquivo de imagem vazio"}), 400

    try:
        embedding = calcular_embedding(imagem_bytes)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 422

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into faces (usuario_id, embedding, modelo)
                values (%s, %s, %s)
                on conflict (usuario_id)
                do update set embedding = excluded.embedding, modelo = excluded.modelo, atualizado_em = now()
                returning usuario_id, modelo, atualizado_em
                """,
                (g.user_id, embedding, MODELO),
            )
            resultado = cur.fetchone()
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify(resultado), 201


@bp.route("/status", methods=["GET"])
@login_required
def status_cadastro():
    """O app usa isso pra saber se o usuário logado já tem rosto cadastrado."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select usuario_id, modelo, atualizado_em from faces where usuario_id = %s",
                (g.user_id,),
            )
            face = cur.fetchone()
    finally:
        put_conn(conn)

    return jsonify({"cadastrado": face is not None, "detalhe": face})


@bp.route("", methods=["DELETE"])
@login_required
def remover_rosto():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("delete from faces where usuario_id = %s", (g.user_id,))
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify({"ok": True})


# ------------------------------------------------------------
# Reconhecimento (chamado pela Raspberry Pi na porta da sala)
# ------------------------------------------------------------

# Distância de cosseno máxima pra considerar que é a mesma pessoa.
# 0 = idêntico, 1 = sem relação. 0.30 é o limiar que o próprio DeepFace
# usa como padrão pro Facenet512 com métrica de cosseno. Subir aceita
# mais parecidos (mais falso positivo = deixa entrar quem não devia);
# baixar exige mais semelhança (mais falso negativo = barra quem devia).
LIMIAR_DISTANCIA = 0.30


def _registrar(cur, evento_id, usuario_id, liberado, motivo):
    """Todo veredito vira log - inclusive (e principalmente) as negativas."""
    cur.execute(
        """
        insert into access_logs (evento_id, usuario_id, tipo, status, dispositivo, motivo)
        values (%s, %s, 'facial', %s, %s, %s)
        """,
        (
            evento_id,
            usuario_id,
            "liberado" if liberado else "negado",
            g.dispositivo_nome,
            motivo,
        ),
    )


# As quatro perguntas do reconhecimento, na ordem em que são feitas.
# Vão pra resposta como `etapa` pra que o leitor da porta saiba ONDE
# parou sem precisar interpretar o texto do motivo - o texto é escrito
# pra humano e pode mudar; isto é contrato.
ETAPAS = ("rosto", "vivacidade", "identidade", "aula", "lista")


def _resposta(liberado, motivo, cur, evento_id=None, usuario_id=None, nome=None, etapa=None):
    # Quadro sem rosto NÃO vira log. O leitor da porta fica perguntando
    # de tempos em tempos, então "não vi ninguém" é o estado normal de um
    # corredor vazio - não uma tentativa de acesso. Registrar isso enchia
    # o access_logs de ruído (numa medição, 85% das linhas) e afogava
    # justamente o que a auditoria precisa enxergar: quem tentou entrar,
    # quando, e por que foi recusado.
    if etapa != "rosto":
        _registrar(cur, evento_id, usuario_id, liberado, motivo)
    corpo = {"liberado": liberado, "motivo": motivo, "etapa": etapa}
    if nome:
        corpo["nome"] = nome
    return corpo


@bp.route("/recognize", methods=["POST"])
@device_required
def reconhecer_rosto():
    """
    Recebe a foto capturada pelo leitor da porta e decide se libera.

    A decisão passa por quatro perguntas, nesta ordem - e qualquer
    resposta negativa vira um access_log com o motivo, porque tentativa
    recusada é exatamente o que um controle de acesso precisa registrar:

      1. dá pra achar um rosto parecido o bastante no banco?
      2. tem alguma aula acontecendo AGORA na sala deste dispositivo?
      3. essa pessoa foi convidada pra essa aula?
      4. tudo certo -> libera e marca presença.

    A imagem não é salva em lugar nenhum, igual ao cadastro.
    """
    if "foto" not in request.files:
        return jsonify({"erro": "Envie a imagem no campo 'foto' (multipart/form-data)"}), 400

    imagem_bytes = request.files["foto"].read()
    if not imagem_bytes:
        return jsonify({"erro": "Arquivo de imagem vazio"}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # (0) Nem chegou a ser um rosto de gente presente.
            #
            # RostoFalsoError vem ANTES do ValueError genérico de propósito:
            # é subclasse dele, e na ordem inversa o except largo engoliria a
            # tentativa de burla e ela viraria etapa "rosto" — que a gente
            # não registra. Foto erguida na câmera some do log, justamente o
            # oposto do que se quer.
            try:
                embedding = calcular_embedding(imagem_bytes)
            except RostoFalsoError as e:
                corpo = _resposta(False, str(e), cur, etapa="vivacidade")
                conn.commit()
                return jsonify(corpo), 200
            except ValueError as e:
                corpo = _resposta(False, str(e), cur, etapa="rosto")
                conn.commit()
                return jsonify(corpo), 200

            # (1) Vizinho mais próximo. O '<=>' do pgvector é distância de
            # cosseno. Esta busca é EXATA (varredura da tabela) de
            # propósito - veja o comentário no schema.sql sobre por que o
            # índice ivfflat foi removido: ele devolvia zero linhas e a
            # porta recusava gente cadastrada.
            cur.execute(
                """
                select f.usuario_id, p.nome, (f.embedding <=> %s::vector) as distancia
                from faces f
                join profiles p on p.id = f.usuario_id
                order by f.embedding <=> %s::vector
                limit 1
                """,
                (embedding.tolist(), embedding.tolist()),
            )
            candidato = cur.fetchone()

            if not candidato or candidato["distancia"] > LIMIAR_DISTANCIA:
                corpo = _resposta(False, "Rosto não reconhecido", cur, etapa="identidade")
                conn.commit()
                return jsonify(corpo), 200

            usuario_id = candidato["usuario_id"]
            nome = candidato["nome"]

            # (2) Aula rolando agora nesta sala. O local é texto livre
            # digitado à mão ("Sala 201", "sala201"), então a comparação
            # normaliza acento, caixa e espaços dos dois lados.
            cur.execute(
                """
                select id, titulo
                from eventos
                where normaliza_local(local) = normaliza_local(%s)
                  and status in ('agendado', 'em_andamento')
                  and now() between data_inicio and data_fim
                order by data_inicio
                limit 1
                """,
                (g.dispositivo_local,),
            )
            evento = cur.fetchone()

            if not evento:
                corpo = _resposta(
                    False,
                    f"Nenhuma aula acontecendo agora em {g.dispositivo_local}",
                    cur, usuario_id=usuario_id, nome=nome, etapa="aula",
                )
                conn.commit()
                return jsonify(corpo), 200

            # (3) Reconhecido, aula existe - mas foi convidado?
            cur.execute(
                """
                select id, status from evento_participantes
                where evento_id = %s and usuario_id = %s
                """,
                (evento["id"], usuario_id),
            )
            participante = cur.fetchone()

            if not participante:
                corpo = _resposta(
                    False, f"Não está na lista de \"{evento['titulo']}\"",
                    cur, evento_id=evento["id"], usuario_id=usuario_id, nome=nome,
                    etapa="lista",
                )
                conn.commit()
                return jsonify(corpo), 200

            # (4) Libera e marca presença.
            cur.execute(
                """
                update evento_participantes
                set status = 'liberado', liberado_em = now()
                where id = %s
                """,
                (participante["id"],),
            )
            corpo = _resposta(
                True, f"Acesso liberado para \"{evento['titulo']}\"",
                cur, evento_id=evento["id"], usuario_id=usuario_id, nome=nome,
            )
            # O leitor mostra o nome da aula na tela; separado do `motivo`
            # pra não ter que recortar texto do lado do dispositivo.
            corpo["evento"] = evento["titulo"]
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify(corpo), 200
