from flask import Blueprint, request, jsonify, g

from services import consentimento
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

# Piso de presença pra aprovação. É a régua acadêmica, não uma escolha de
# produto - e o app usa a mesma em corDaFrequencia().
MINIMO_FREQUENCIA = 0.75


def resumo_frequencia(total: int, presencas: int, previstas: int) -> dict:
    """
    Transforma a contagem crua no que a pessoa precisa saber.

    `total` são as aulas já encerradas, `previstas` incluem as que ainda vão
    acontecer. A diferença é o que separa "você está com 60%" de "você ainda
    pode faltar 2" - a primeira é um retrato do passado, a segunda é a única
    que dá pra agir em cima, e é ela que evita a descoberta em julho.

    O limite sai das aulas PREVISTAS porque faltar 1 de 2 aulas dadas não é
    reprovação nenhuma se o semestre tem 30. Calcular sobre as encerradas
    faria o app gritar em março com quem está bem.
    """
    faltas = total - presencas
    # Quantas faltas cabem no semestre inteiro. int() trunca pra baixo de
    # propósito: com 30 aulas previstas cabem 7 faltas, não 7,5.
    limite = int(previstas * (1 - MINIMO_FREQUENCIA))
    return {
        "total": total,
        "presencas": presencas,
        "faltas": faltas,
        # None (e não 0) quando ainda não houve aula: "0%" mentiria.
        "percentual": round(presencas * 100 / total) if total else None,
        "previstas": previstas,
        "limite_faltas": limite,
        "faltas_restantes": max(0, limite - faltas),
        # Passou do que as aulas MARCADAS comportam.
        #
        # O `limite >= 1` não é detalhe: `previstas` são as aulas já criadas,
        # não o tamanho do semestre - o sistema não sabe quantas aulas a
        # disciplina vai ter. Com 1 ou 2 aulas marcadas o limite é zero, e
        # sem essa condição QUALQUER pessoa que perdesse a primeira aula do
        # semestre já apareceria reprovada. Foi o que aconteceu rodando
        # contra o banco real: as três pessoas cadastradas, com uma falta
        # cada, saíram todas reprovadas.
        #
        # Enquanto o professor não marcar aulas o bastante pra caber uma
        # falta, não há o que afirmar - e afirmar errado ensina a ignorar o
        # aviso.
        "reprovado_por_falta": limite >= 1 and faltas > limite,
    }


# ------------------------------------------------------------
# Consentimento (LGPD) - ver services/consentimento.py
# ------------------------------------------------------------

def ultimo_consentimento(cur, usuario_id):
    """A linha mais recente da pessoa, ou None. Usada aqui e em /faces."""
    cur.execute(
        """
        select versao, aceito_em, revogado_em
        from consentimentos where usuario_id = %s
        order by aceito_em desc limit 1
        """,
        (usuario_id,),
    )
    return cur.fetchone()


@bp.route("/me/consentimento", methods=["GET"])
@login_required
def meu_consentimento():
    """
    O texto atual e se a pessoa já consentiu com ELE.

    O texto vem do servidor, e não embutido no app, por dois motivos: um
    APK antigo mostraria uma versão diferente da que o servidor registra, e
    corrigir uma frase passaria a exigir publicar app novo.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            registro = ultimo_consentimento(cur, g.user_id)
    finally:
        put_conn(conn)

    return jsonify({
        "versao": consentimento.VERSAO,
        "titulo": consentimento.TITULO,
        "texto": consentimento.TEXTO,
        "precisa_consentir": consentimento.precisa_consentir(registro),
        "aceito_em": registro["aceito_em"] if registro else None,
        "versao_aceita": registro["versao"] if registro else None,
    })


@bp.route("/me/consentimento", methods=["POST"])
@login_required
def consentir():
    """
    Registra o aceite da versão ATUAL.

    A versão gravada é a do servidor, nunca a que o cliente mandar: senão
    bastaria um app dizer "aceitei a versão 2030" pra nunca mais ser
    perguntado.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into consentimentos (usuario_id, versao)
                values (%s, %s)
                returning versao, aceito_em
                """,
                (g.user_id, consentimento.VERSAO),
            )
            registro = cur.fetchone()
        conn.commit()
    finally:
        put_conn(conn)

    return jsonify(registro), 201


@bp.route("/me/frequencia", methods=["GET"])
@login_required
def minha_frequencia():
    """Quantas das aulas já encerradas em que fui convidado eu realmente frequentei."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Por turma, porque é assim que a reprovação por falta funciona:
            # 75% é por disciplina, não da vida acadêmica somada. O número
            # geral pode dizer 80% enquanto a pessoa está com 50% numa
            # matéria - foi o que este app mostrou até hoje.
            #
            # A turma vem de evento_participantes, e não de eventos: é o
            # convite que carrega de qual turma aquela aula veio. Convite
            # manual fica com turma_id nulo e cai num grupo "avulsas".
            cur.execute(
                f"""
                select ep.turma_id, t.nome as turma,
                       count(*) filter (where {_AULAS_QUE_CONTAM}) as total,
                       count(*) filter (where {_AULAS_QUE_CONTAM}
                                          and ep.status = 'liberado') as presencas,
                       count(*) filter (where e.status != 'cancelado') as previstas
                from evento_participantes ep
                join eventos e on e.id = ep.evento_id
                left join turmas t on t.id = ep.turma_id
                where ep.usuario_id = %s
                group by ep.turma_id, t.nome
                order by t.nome nulls last
                """,
                (g.user_id,),
            )
            linhas = cur.fetchall()
    finally:
        put_conn(conn)

    turmas = [
        {
            "turma_id": l["turma_id"],
            "turma": l["turma"] or "Aulas avulsas",
            **resumo_frequencia(l["total"], l["presencas"], l["previstas"]),
        }
        for l in linhas
    ]

    # O agregado continua no mesmo lugar do JSON pra não quebrar app já
    # instalado, mas agora é o resumo, não a informação: quem decide
    # aprovação é a linha da disciplina.
    geral = resumo_frequencia(
        sum(t["total"] for t in turmas),
        sum(t["presencas"] for t in turmas),
        sum(t["previstas"] for t in turmas),
    )
    return jsonify({**geral, "turmas": turmas})


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
