import psycopg2
from flask import Blueprint, request, jsonify, g

from services import cache_local, fila_offline
from utils.auth_middleware import login_required
from utils.device_auth import device_required
from utils.db import (
    get_conn,
    marcar_com_banco,
    marcar_sem_banco,
    put_conn,
    sem_banco,
)
from services.face_service import (
    LIMIAR_DISTANCIA,
    MODELO,
    RostoFalsoError,
    calcular_embedding,
    e_a_mesma_pessoa,
)

bp = Blueprint("faces", __name__, url_prefix="/api/faces")

# LIMIAR_DISTANCIA e e_a_mesma_pessoa vivem em services/face_service.py e são
# reexportados aqui: a decisão offline (services/cache_local.py) precisa da
# mesma definição, e serviço importando rota daria import circular.

# Teto de capturas por pessoa. Não é limitação técnica - é pra a tabela não
# crescer sem controle e pra a varredura exata (sem índice, ver schema.sql)
# continuar rápida: o custo do reconhecimento é linear no total de linhas.
MAX_FOTOS_POR_PESSOA = 5


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
#
# Todo veredito passa por três etapas separadas de propósito:
#
#   decidir   -> quem é, tem aula aqui agora, foi convidado
#   gravar    -> log e presença
#   responder -> o que o totem da porta mostra
#
# A separação existe porque cada uma tem um plano B diferente quando o
# Postgres está fora de alcance: decidir cai pra cópia local, gravar cai
# pra fila em arquivo, e responder não muda nada - o texto que a pessoa lê
# na porta é o mesmo com internet ou sem.
# ------------------------------------------------------------

# As cinco perguntas do reconhecimento, na ordem em que são feitas.
# Vão pra resposta como `etapa` pra que o leitor da porta saiba ONDE
# parou sem precisar interpretar o texto do motivo - o texto é escrito
# pra humano e pode mudar; isto é contrato.
ETAPAS = ("rosto", "vivacidade", "identidade", "aula", "lista")


def _decidir_no_banco(cur, embedding) -> dict:
    """
    As três perguntas em SQL.

    Devolve o MESMO formato de `cache_local.decidir`, com as mesmas
    mensagens - as duas funções são pra ser lidas lado a lado. Quando uma
    mudar, a outra tem que mudar junto, senão a porta passa a dizer coisas
    diferentes dependendo de a internet estar de pé.
    """
    # (1) Vizinho mais próximo. O '<=>' do pgvector é distância de
    # cosseno. Esta busca é EXATA (varredura da tabela) de propósito -
    # veja o comentário no schema.sql sobre por que o índice ivfflat foi
    # removido: ele devolvia zero linhas e a porta recusava gente
    # cadastrada.
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
        return {"liberado": False, "motivo": "Rosto não reconhecido", "etapa": "identidade"}

    usuario_id = candidato["usuario_id"]
    nome = candidato["nome"]

    # (2) Aula rolando agora nesta sala. O local é texto livre digitado à
    # mão ("Sala 201", "sala201"), então a comparação normaliza acento,
    # caixa e espaços dos dois lados.
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
        return {
            "liberado": False,
            "motivo": f"Nenhuma aula acontecendo agora em {g.dispositivo_local}",
            "etapa": "aula",
            "nome": nome,
            "usuario_id": usuario_id,
        }

    # (3) Reconhecido, aula existe - mas foi convidado?
    cur.execute(
        "select id from evento_participantes where evento_id = %s and usuario_id = %s",
        (evento["id"], usuario_id),
    )
    if not cur.fetchone():
        return {
            "liberado": False,
            "motivo": f"Não está na lista de \"{evento['titulo']}\"",
            "etapa": "lista",
            "nome": nome,
            "usuario_id": usuario_id,
            "evento_id": evento["id"],
        }

    return {
        "liberado": True,
        "motivo": f"Acesso liberado para \"{evento['titulo']}\"",
        "etapa": None,
        "nome": nome,
        "usuario_id": usuario_id,
        "evento_id": evento["id"],
        "evento": evento["titulo"],
    }


def _decidir_pela_copia(embedding) -> dict:
    copia = cache_local.carregar()
    if not copia:
        # Sem banco e sem cópia não dá pra afirmar nada sobre quem está na
        # frente da câmera. Negar é a única resposta honesta, e o motivo
        # diz que o problema é o servidor - não a pessoa.
        return {
            "liberado": False,
            "motivo": "Servidor sem banco e sem cópia local",
            "etapa": "identidade",
        }

    return cache_local.decidir(
        copia,
        embedding,
        {"local": g.dispositivo_local, "local_norm": g.dispositivo_local_norm},
    )


def _decidir(embedding) -> dict:
    """Pelo banco quando ele responde; pela cópia local quando não."""
    if not sem_banco():
        conn = None
        try:
            conn = get_conn()
            with conn.cursor() as cur:
                decisao = _decidir_no_banco(cur, embedding)
            marcar_com_banco()
            return decisao
        except psycopg2.Error as e:
            # Não é 500: é exatamente o caso pro qual a cópia local existe.
            print(f"[porta] banco fora de alcance, decidindo pela cópia local: {e}",
                  flush=True)
            marcar_sem_banco()
        finally:
            if conn is not None:
                put_conn(conn)

    return _decidir_pela_copia(embedding)


def _gravar(decisao: dict):
    """
    Log e presença - no banco quando dá, na fila em arquivo quando não.

    Nunca levanta: uma falha ao registrar não pode virar erro na cara de
    quem está na porta. O que ela não pode é sumir com o registro, e é a
    fila que garante isso.
    """
    # Quadro sem rosto NÃO vira log. O leitor da porta fica perguntando de
    # tempos em tempos, então "não vi ninguém" é o estado normal de um
    # corredor vazio - não uma tentativa de acesso. Registrar isso enchia o
    # access_logs de ruído (numa medição, 85% das linhas) e afogava
    # justamente o que a auditoria precisa enxergar: quem tentou entrar,
    # quando, e por que foi recusado.
    if decisao.get("etapa") == "rosto":
        return

    if sem_banco():
        _enfileirar(decisao)
        return

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into access_logs
                    (evento_id, usuario_id, tipo, status, dispositivo, motivo)
                values (%s, %s, 'facial', %s, %s, %s)
                """,
                (
                    decisao.get("evento_id"),
                    decisao.get("usuario_id"),
                    "liberado" if decisao["liberado"] else "negado",
                    g.dispositivo_nome,
                    decisao["motivo"],
                ),
            )

            if decisao["liberado"] and decisao.get("evento_id"):
                cur.execute(
                    """
                    update evento_participantes
                    set status = 'liberado', liberado_em = now()
                    where evento_id = %s and usuario_id = %s
                    """,
                    (decisao["evento_id"], decisao["usuario_id"]),
                )
        conn.commit()
        marcar_com_banco()
        _manutencao(conn)
    except psycopg2.Error as e:
        print(f"[porta] não deu pra gravar no banco, indo pra fila: {e}", flush=True)
        marcar_sem_banco()
        _enfileirar(decisao)
    finally:
        if conn is not None:
            put_conn(conn)


def _enfileirar(decisao: dict):
    fila_offline.enfileirar(
        liberado=decisao["liberado"],
        motivo=decisao["motivo"],
        dispositivo=g.dispositivo_nome,
        evento_id=decisao.get("evento_id"),
        usuario_id=decisao.get("usuario_id"),
    )


def _manutencao(conn):
    """
    De carona numa passagem que já deu certo: sobe o que ficou na fila e
    renova a cópia local se estiver velha.

    Fica aqui, e não numa thread de fundo, porque a porta sendo usada é o
    único momento em que isso importa - e é o momento em que já se sabe que
    o banco responde. Falha aqui não pode derrubar a resposta: cópia velha
    ou fila que espera mais um pouco são bem menos graves que um erro na
    cara de quem está na porta.
    """
    try:
        with conn.cursor() as cur:
            enviados = fila_offline.enviar(cur)
            renovou = cache_local.atualizar_se_velho(cur)
        conn.commit()
        if enviados:
            print(f"[porta] {enviados} veredito(s) offline subiram pro banco", flush=True)
        if renovou:
            print("[porta] cópia local renovada", flush=True)
    except Exception as e:
        conn.rollback()
        print(f"[porta] manutenção adiada: {e}", flush=True)


def _corpo(decisao: dict) -> dict:
    corpo = {
        "liberado": decisao["liberado"],
        "motivo": decisao["motivo"],
        "etapa": decisao.get("etapa"),
    }
    if decisao.get("nome"):
        corpo["nome"] = decisao["nome"]
    # O leitor mostra o nome da aula na tela; separado do `motivo` pra não
    # ter que recortar texto do lado do dispositivo.
    if decisao.get("evento"):
        corpo["evento"] = decisao["evento"]
    return corpo


@bp.route("/recognize", methods=["POST"])
@device_required
def reconhecer_rosto():
    """
    Recebe a foto capturada pelo leitor da porta e decide se libera.

    A decisão passa por quatro perguntas, nesta ordem - e qualquer
    resposta negativa vira um access_log com o motivo, porque tentativa
    recusada é exatamente o que um controle de acesso precisa registrar:

      1. é gente presente, e não uma foto erguida na frente da câmera?
      2. dá pra achar um rosto parecido o bastante no cadastro?
      3. tem alguma aula acontecendo AGORA na sala deste dispositivo?
      4. essa pessoa foi convidada pra essa aula?

    Sem internet, as perguntas continuam as mesmas: quem responde passa a
    ser a cópia local (services/cache_local.py) e o registro vai pra fila
    (services/fila_offline.py) em vez do Postgres.

    A imagem não é salva em lugar nenhum, igual ao cadastro.
    """
    if "foto" not in request.files:
        return jsonify({"erro": "Envie a imagem no campo 'foto' (multipart/form-data)"}), 400

    imagem_bytes = request.files["foto"].read()
    if not imagem_bytes:
        return jsonify({"erro": "Arquivo de imagem vazio"}), 400

    # (0) Nem chegou a ser um rosto de gente presente. Não depende de banco
    # nenhum: é só a foto e os modelos carregados aqui.
    #
    # RostoFalsoError vem ANTES do ValueError genérico de propósito: é
    # subclasse dele, e na ordem inversa o except largo engoliria a
    # tentativa de burla e ela viraria etapa "rosto" — que a gente não
    # registra. Foto erguida na câmera some do log, justamente o oposto do
    # que se quer.
    try:
        embedding = calcular_embedding(imagem_bytes)
    except RostoFalsoError as e:
        decisao = {"liberado": False, "motivo": str(e), "etapa": "vivacidade"}
    except ValueError as e:
        decisao = {"liberado": False, "motivo": str(e), "etapa": "rosto"}
    else:
        decisao = _decidir(embedding)

    _gravar(decisao)
    return jsonify(_corpo(decisao)), 200
