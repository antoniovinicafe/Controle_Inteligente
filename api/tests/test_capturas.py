"""Listar e apagar UMA captura.

POR QUE ESTES TESTES EXISTEM
Duas coisas aqui erram calado.

A primeira é o `usuario_id` no where do delete. Ao lado de um id primário
ele parece redundante — e é o que impede que qualquer pessoa logada apague
a captura de qualquer outra passando o número. Se alguém "limpar" essa
consulta, nada quebra, nenhum teste comum falha, e a rota vira uma
ferramenta de sabotagem: some com o rosto do colega e ele não entra mais.

A segunda é o embedding vazar na listagem. É o dado biométrico em si; a tela
não tem o que fazer com ele e ninguém notaria um campo a mais no JSON.

As rotas exigem login, então os testes chamam a função por baixo do
decorador (`__wrapped__`) com o g.user_id posto à mão. O banco é um dublê.
"""

import pytest
from flask import Flask, g

from routes import faces

EU = "11111111-1111-1111-1111-111111111111"


class CursorDuble:
    def __init__(self, linhas=(), rowcount=0, consentimento=None):
        self.linhas = list(linhas)
        self.rowcount = rowcount
        self.consentimento = consentimento
        self.comandos = []

    def execute(self, sql, params=None):
        self.comandos.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.consentimento

    def fetchall(self):
        return self.linhas

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ConexaoDuble:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1


@pytest.fixture
def banco(monkeypatch):
    def montar(linhas=(), rowcount=0):
        cursor = CursorDuble(linhas, rowcount)
        monkeypatch.setattr(faces, "get_conn", lambda: ConexaoDuble(cursor))
        monkeypatch.setattr(faces, "put_conn", lambda c: None)
        montar.cursor = cursor
        return cursor
    return montar


def chamar(rota, *args):
    """Executa a rota sem o decorador de login, como se eu estivesse logado."""
    app = Flask(__name__)
    with app.test_request_context():
        g.user_id = EU
        return rota.__wrapped__(*args)


# ------------------------------------------------------------
# Apagar
# ------------------------------------------------------------

def test_apaga_a_captura_e_confirma(banco):
    banco(rowcount=1)
    corpo = chamar(faces.remover_captura, 8)
    assert corpo.json == {"ok": True}


def test_o_delete_exige_que_a_captura_seja_minha(banco):
    # A invariante que sustenta a rota inteira. Se o usuario_id sumir do
    # where, qualquer um apaga o rosto de qualquer um.
    cursor = banco(rowcount=1)
    chamar(faces.remover_captura, 8)

    (sql, params), = [c for c in cursor.comandos if "delete from faces" in c[0]]
    assert "usuario_id = %s" in sql
    assert EU in params


def test_captura_de_outra_pessoa_nao_e_apagada(banco):
    # O dublê devolve rowcount 0, que é o que o Postgres devolve quando o
    # id existe mas é de outra conta.
    banco(rowcount=0)
    corpo, status = chamar(faces.remover_captura, 8)
    assert status == 404


def test_a_recusa_nao_conta_se_o_id_existe(banco):
    # 403 diria "existe, mas não é sua" - e transformaria a rota num
    # consultor de quem tem rosto cadastrado.
    banco(rowcount=0)
    _, status = chamar(faces.remover_captura, 8)
    assert status != 403


# ------------------------------------------------------------
# Listar
# ------------------------------------------------------------

def linha(id, distancia_irma):
    return {
        "id": id,
        "modelo": "Facenet512",
        "atualizado_em": "2026-08-13T18:04:28+00:00",
        "distancia_irma": distancia_irma,
    }


def test_a_captura_intrusa_aparece_marcada(banco):
    # O caso real de 13/08: 0,895 de todas as outras.
    banco([linha(8, 0.895), linha(9, 0.15)])
    corpo = chamar(faces.listar_rostos)
    marcadas = [c["id"] for c in corpo.json["capturas"] if c["estranha"]]
    assert marcadas == [8]


def test_captura_normal_nao_e_marcada(banco):
    # 0,52 foi o par legítimo mais distante já medido: não pode virar
    # sugestão de apagar.
    banco([linha(9, 0.52)])
    corpo = chamar(faces.listar_rostos)
    assert corpo.json["capturas"][0]["estranha"] is False


def test_captura_unica_nao_e_marcada(banco):
    # Sem irmã não há com o que comparar, e distancia_irma vem nula. Marcar
    # aqui sugeriria apagar a única foto da pessoa.
    banco([linha(9, None)])
    corpo = chamar(faces.listar_rostos)
    assert corpo.json["capturas"][0]["estranha"] is False


def test_a_listagem_nunca_devolve_o_embedding(banco):
    # A resposta é montada direto das linhas do banco, então acrescentar o
    # embedding ao select o faria aparecer aqui - é o que este teste pega.
    # (A consulta USA f.embedding pra calcular a distância entre irmãs; o
    # que não pode é ele virar coluna devolvida.)
    banco([linha(9, 0.15)])
    corpo = chamar(faces.listar_rostos)
    assert "embedding" not in corpo.json["capturas"][0]


def test_a_listagem_diz_o_teto(banco):
    banco([linha(9, None)])
    corpo = chamar(faces.listar_rostos)
    assert corpo.json["maximo"] == faces.MAX_FOTOS_POR_PESSOA


# ------------------------------------------------------------
# Consentimento: a regra é do servidor, não da tela
# ------------------------------------------------------------

def test_sem_consentimento_o_rosto_nao_entra(banco, monkeypatch):
    # A checagem tem que ser aqui, e não só na tela do app: se quem
    # decidisse fosse o cliente, um APK antigo - ou qualquer coisa que saiba
    # fazer um POST - gravaria biometria sem consentimento nenhum, e o
    # registro no banco viraria enfeite.
    banco()
    monkeypatch.setattr(faces.consentimento, "precisa_consentir", lambda r: True)

    app = Flask(__name__)
    with app.test_request_context(
        data={"foto": (open(__file__, "rb"), "rosto.jpg")},
        content_type="multipart/form-data",
    ):
        g.user_id = EU
        corpo, status = faces.cadastrar_rosto.__wrapped__()

    assert status == 403
    assert corpo.json["consentimento_pendente"] is True


def test_a_foto_nem_chega_no_modelo_sem_consentimento(banco, monkeypatch):
    # A ORDEM importa: transformar a foto em vetor já é tratar dado
    # biométrico. Checar depois seria processar primeiro e pedir licença
    # depois - exatamente o que a LGPD proíbe pra dado sensível. Este teste
    # falha se alguém reordenar a rota.
    banco()
    monkeypatch.setattr(faces.consentimento, "precisa_consentir", lambda r: True)

    def nao_deveria_rodar(*a, **k):
        raise AssertionError("o embedding foi calculado sem consentimento")

    monkeypatch.setattr(faces, "calcular_embedding", nao_deveria_rodar)

    app = Flask(__name__)
    with app.test_request_context(
        data={"foto": (open(__file__, "rb"), "rosto.jpg")},
        content_type="multipart/form-data",
    ):
        g.user_id = EU
        _, status = faces.cadastrar_rosto.__wrapped__()
    assert status == 403


def test_apagar_o_rosto_revoga_o_consentimento(banco):
    # Revogar e "apagar meus dados" são a mesma ação: dois botões criariam
    # um estado impossível (consentido sem rosto, rosto sem consentimento).
    cursor = banco(rowcount=1)
    chamar(faces.remover_rosto)
    assert [c for c in cursor.comandos if "update consentimentos" in c[0]]


def test_a_revogacao_nao_apaga_a_prova(banco):
    # O registro antigo é carimbado, não removido: ele é a prova de que o
    # tratamento anterior era legítimo, e some junto com o dado seria
    # destruir a própria defesa.
    cursor = banco(rowcount=1)
    chamar(faces.remover_rosto)
    assert not [c for c in cursor.comandos if "delete from consentimentos" in c[0]]
    (sql, _), = [c for c in cursor.comandos if "update consentimentos" in c[0]]
    assert "revogado_em = now()" in sql
