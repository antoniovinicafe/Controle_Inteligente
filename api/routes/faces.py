from flask import Blueprint, request, jsonify, g

from utils.auth_middleware import login_required
from utils.device_auth import device_required
from utils.db import get_conn, put_conn
from services.face_service import calcular_embedding, MODELO, RostoFalsoError

bp = Blueprint("faces", __name__, url_prefix="/api/faces")

# Distância de cosseno máxima pra considerar que é a mesma pessoa.
# 0 = idêntico, 1 = sem relação. 0.30 é o limiar que o próprio DeepFace
# usa como padrão pro Facenet512 com métrica de cosseno. Subir aceita
# mais parecidos (mais falso positivo = deixa entrar quem não devia);
# baixar exige mais semelhança (mais falso negativo = barra quem devia).
LIMIAR_DISTANCIA = 0.30

# Teto de capturas por pessoa. Não é limitação técnica - é pra a tabela não
# crescer sem controle e pra a varredura exata (sem índice, ver schema.sql)
# continuar rápida: o custo do reconhecimento é linear no total de linhas.
MAX_FOTOS_POR_PESSOA = 5


def e_a_mesma_pessoa(distancia: float) -> bool:
    """
    Único lugar do sistema que decide "esses dois rostos são a mesma pessoa".

    A porta e o cadastro usam a MESMA definição, de propósito e em direções
    opostas: a porta libera quando é a mesma pessoa, o cadastro recusa. É essa
    simetria que sustenta a garantia de que duas contas nunca guardam rostos
    que o leitor confundiria - se as duas leituras pudessem discordar, daria
    pra cadastrar um par que a porta depois trocasse.
    """
    return distancia <= LIMIAR_DISTANCIA


# Distância máxima entre uma captura nova e a captura mais próxima que a
# própria pessoa já tem.
#
# NÃO é o limiar do reconhecimento, e não poderia ser: duas fotos legítimas
# da mesma pessoa passam de 0,30 com folga - é justamente por isso que se
# guarda mais de uma. Exigir 0,30 aqui recusaria a segunda foto de quase
# todo mundo, logo a que existe pra cobrir a outra condição de luz.
#
# O que se quer barrar é o vetor que não é aquele rosto. Medido em
# 13/08/2026 (ver medir_rostos.py): entre 5 capturas legítimas da mesma
# pessoa, o par mais distante deu 0,520; uma captura intrusa na mesma conta
# estava a 0,895 da mais próxima. 0,70 fica entre as duas com folga parecida
# dos dois lados.
#
# O 0,520 é o número que manda aqui, não o 0,23 da irmã mais próxima: quem
# tem UMA captura só e vai tirar a segunda em outra condição está justamente
# no pior caso, sem outras fotos pra ficar perto. Apertar isso recusaria a
# segunda foto - logo a que existe pra cobrir a outra luz.
LIMIAR_ROSTO_ESTRANHO = 0.70


def e_o_mesmo_rosto(distancia: float) -> bool:
    """A captura nova é a mesma cara das que a conta já tem?"""
    return distancia <= LIMIAR_ROSTO_ESTRANHO


def _propria_mais_proxima(cur, usuario_id, embedding):
    """Distância até a captura mais próxima que a própria pessoa já tem."""
    cur.execute(
        """
        select min(embedding <=> %s::vector) as distancia
        from faces where usuario_id = %s
        """,
        (embedding.tolist(), usuario_id),
    )
    return cur.fetchone()["distancia"]


def _dono_parecido(cur, usuario_id, embedding):
    """
    O rosto mais próximo deste que pertence a OUTRA conta, se houver.

    Mesma busca do reconhecimento, tirando as capturas da própria pessoa -
    senão a segunda foto de alguém seria recusada por parecer com a primeira.
    """
    cur.execute(
        """
        select f.usuario_id, (f.embedding <=> %s::vector) as distancia
        from faces f
        where f.usuario_id <> %s
        order by f.embedding <=> %s::vector
        limit 1
        """,
        (embedding.tolist(), usuario_id, embedding.tolist()),
    )
    return cur.fetchone()


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
            # Cada foto ACRESCENTA em vez de substituir: mais capturas da
            # mesma pessoa (luz, ângulo, óculos) cobrem a variação real e a
            # busca compara contra a melhor delas.
            cur.execute("select count(*) as n from faces where usuario_id = %s", (g.user_id,))
            ja_tem = cur.fetchone()["n"]
            if ja_tem >= MAX_FOTOS_POR_PESSOA:
                return jsonify({
                    "erro": f"Você já tem {ja_tem} fotos cadastradas, que é o "
                            "máximo. Remova as atuais pra cadastrar de novo."
                }), 409

            # A foto nova é da mesma cara das que já estão aqui?
            #
            # Sem isto, qualquer rosto que ainda não esteja em outra conta
            # entra em silêncio - e foi o que aconteceu em 13/08/2026: um
            # vetor a 0,895 de todas as outras capturas da pessoa. Não
            # atrapalha o dono, porque a porta compara contra a captura mais
            # próxima e nunca escolhe essa; fica é como uma chave a mais,
            # capaz de abrir a porta no nome dele pra quem se parecer com
            # ela. Não dá pra apagar uma captura só, então barrar na entrada
            # é o único momento barato de resolver.
            if ja_tem:
                distancia = _propria_mais_proxima(cur, g.user_id, embedding)
                if not e_o_mesmo_rosto(distancia):
                    return jsonify({
                        "erro": "Essa foto não parece a mesma pessoa das suas "
                                "outras. Tente de novo de frente, com o rosto "
                                "inteiro no quadro e mais luz."
                    }), 422

            # Esse rosto já é de outra conta?
            #
            # Sem isto dá pra cadastrar o rosto de um colega na própria conta e
            # ganhar a presença dele: ele chega na porta, o leitor acha a linha
            # de quem cadastrou e marca a pessoa errada como presente. É a
            # fraude que o reconhecimento facial deveria justamente eliminar -
            # o "assina a lista por mim" de sempre, agora automatizado.
            #
            # Recusar o segundo cadastro basta: o rosto continua valendo pra
            # quem o cadastrou primeiro, e nenhuma outra conta consegue
            # reivindicá-lo.
            conflito = _dono_parecido(cur, g.user_id, embedding)
            if conflito and e_a_mesma_pessoa(conflito["distancia"]):
                # De quem é o rosto não sai daqui. Confirmar "esse rosto é do
                # fulano" transformaria o cadastro num consultor de quem está
                # cadastrado - qualquer um poderia testar rostos alheios.
                return jsonify({
                    "erro": "Esse rosto já está cadastrado em outra conta. "
                            "Se isso for engano, procure um administrador."
                }), 409

            cur.execute(
                """
                insert into faces (usuario_id, embedding, modelo)
                values (%s, %s, %s)
                returning usuario_id, modelo, atualizado_em
                """,
                (g.user_id, embedding, MODELO),
            )
            resultado = cur.fetchone()
            resultado["total_fotos"] = ja_tem + 1
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
                """
                select count(*) as total, max(atualizado_em) as atualizado_em,
                       max(modelo) as modelo
                from faces where usuario_id = %s
                """,
                (g.user_id,),
            )
            r = cur.fetchone()
    finally:
        put_conn(conn)

    total = r["total"]
    return jsonify({
        "cadastrado": total > 0,
        "total": total,
        "maximo": MAX_FOTOS_POR_PESSOA,
        # `detalhe` mantém o formato antigo pra não quebrar app já instalado.
        "detalhe": None if total == 0 else {
            "usuario_id": g.user_id,
            "modelo": r["modelo"],
            "atualizado_em": r["atualizado_em"],
        },
    })


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

            if not candidato or not e_a_mesma_pessoa(candidato["distancia"]):
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
