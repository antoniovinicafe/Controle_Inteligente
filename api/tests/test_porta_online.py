"""A porta com banco: a mesma prova que o modo offline já tinha.

POR QUE ESTES TESTES EXISTEM
O caminho online foi reescrito quando o modo offline entrou — decidir,
gravar e responder passaram a ser três coisas separadas, e o log saiu do
meio da sequência de consultas. É o caminho que roda em 99% das leituras, e
ficou com menos prova que o de exceção: o offline ganhou um teste de rota
inteira, este aqui não tinha nenhum.

Além do óbvio (cada etapa devolvendo o veredito certo), dois pontos que
quebram calados:

- quadro sem rosto NÃO pode virar log. Corredor vazio é o estado normal de
  um leitor que pergunta a cada segundo; registrar isso enche o access_logs
  de ruído e afoga o que a auditoria precisa ver. Já foi 85% das linhas uma
  vez.
- os dois caminhos têm que responder IGUAL. O totem lê estes campos, e o
  texto na porta não pode mudar porque a internet caiu. O último teste
  compara as duas respostas para o mesmo cenário.

O banco é um dublê que responde por trecho de SQL e guarda o que recebeu.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from flask import Flask

from routes import faces
from services import cache_local, fila_offline
from utils import device_auth

CHAVE = "chave-do-leitor-de-teste"
CHAVE_HASH = hashlib.sha256(CHAVE.encode()).hexdigest()
ANA = "11111111-1111-1111-1111-111111111111"

DISPOSITIVO = {"id": 1, "nome": "leitor-quadra", "local": "Quadra",
               "local_norm": "quadra", "ativo": True}
EVENTO = {"id": 77, "titulo": "Cálculo I"}


def vetor(*valores):
    v = [0.0] * 512
    for i, x in enumerate(valores):
        v[i] = x
    return v


class CursorDuble:
    """Responde pela consulta que reconhecer, e guarda tudo que recebeu."""

    def __init__(self, respostas):
        self.respostas = respostas
        self.comandos = []
        self._ultimo = None

    def execute(self, sql, params=None):
        sql_limpo = " ".join(sql.split())
        self.comandos.append((sql_limpo, params))
        self._ultimo = None
        for trecho, resposta in self.respostas.items():
            if trecho in sql_limpo:
                self._ultimo = resposta
                return

    def fetchone(self):
        return self._ultimo

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def de(self, trecho):
        return [c for c in self.comandos if trecho in c[0]]


class ConexaoDuble:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


@pytest.fixture
def porta(monkeypatch, tmp_path):
    """Cliente HTTP da porta, com banco (dublê) respondendo."""
    app = Flask(__name__)
    app.register_blueprint(faces.bp)

    monkeypatch.setattr(faces, "sem_banco", lambda: False)
    monkeypatch.setattr(device_auth, "sem_banco", lambda: False)
    monkeypatch.setattr(fila_offline, "ARQUIVO", tmp_path / "pendentes.jsonl")
    # A manutenção pega carona na leitura e faria o dublê responder consultas
    # que este teste não descreve; ela tem os seus próprios testes.
    monkeypatch.setattr(cache_local, "atualizar_se_velho", lambda *a, **k: False)

    def montar(candidato=None, evento=None, participante=None, erro=None):
        cursor = CursorDuble({
            "from dispositivos": DISPOSITIVO,
            "from faces f": candidato,
            "from eventos": evento,
            "from evento_participantes": participante,
        })
        conexao = ConexaoDuble(cursor)
        monkeypatch.setattr(faces, "get_conn", lambda: conexao)
        monkeypatch.setattr(device_auth, "get_conn", lambda: conexao)
        monkeypatch.setattr(faces, "put_conn", lambda c: None)
        monkeypatch.setattr(device_auth, "put_conn", lambda c: None)

        def embedding(*a, **k):
            if erro:
                raise erro
            return np.array(vetor(1.0, 0.0), dtype=np.float32)

        monkeypatch.setattr(faces, "calcular_embedding", embedding)
        montar.cursor = cursor
        return app.test_client()

    return montar


def bater_na_porta(cliente):
    return cliente.post(
        "/api/faces/recognize",
        headers={"X-Device-Key": CHAVE},
        data={"foto": (open(__file__, "rb"), "captura.jpg")},
        content_type="multipart/form-data",
    )


RECONHECIDO = {"usuario_id": ANA, "nome": "Ana", "distancia": 0.05}
LONGE = {"usuario_id": ANA, "nome": "Ana", "distancia": 0.62}


# ------------------------------------------------------------
# As quatro etapas
# ------------------------------------------------------------

def test_convidado_entra(porta):
    r = bater_na_porta(porta(RECONHECIDO, EVENTO, {"id": 5}))
    assert r.json["liberado"] is True
    assert r.json["nome"] == "Ana"
    assert r.json["evento"] == "Cálculo I"


def test_reconhecido_mas_nao_convidado(porta):
    r = bater_na_porta(porta(RECONHECIDO, EVENTO, None))
    assert r.json["liberado"] is False
    assert r.json["etapa"] == "lista"
    assert r.json["nome"] == "Ana"


def test_rosto_longe_demais_nao_e_reconhecido(porta):
    r = bater_na_porta(porta(LONGE, EVENTO, {"id": 5}))
    assert r.json["etapa"] == "identidade"
    assert "nome" not in r.json  # não diz de quem quase foi


def test_sem_aula_agora(porta):
    r = bater_na_porta(porta(RECONHECIDO, None, None))
    assert r.json["etapa"] == "aula"
    assert "Quadra" in r.json["motivo"]


def test_foto_erguida_na_camera(porta):
    from services.face_service import RostoFalsoError

    r = bater_na_porta(porta(erro=RostoFalsoError("Isso parece uma foto (90%)")))
    assert r.json["etapa"] == "vivacidade"


# ------------------------------------------------------------
# O que vira registro, e o que não vira
# ------------------------------------------------------------

def test_liberacao_grava_log_e_presenca(porta):
    cliente = porta(RECONHECIDO, EVENTO, {"id": 5})
    bater_na_porta(cliente)
    assert len(porta.cursor.de("insert into access_logs")) == 1
    assert len(porta.cursor.de("update evento_participantes")) == 1


def test_negativa_grava_log_mas_nao_presenca(porta):
    cliente = porta(RECONHECIDO, EVENTO, None)
    bater_na_porta(cliente)
    assert len(porta.cursor.de("insert into access_logs")) == 1
    assert porta.cursor.de("update evento_participantes set") == []


def test_quadro_sem_rosto_nao_vira_log(porta):
    # Corredor vazio é rotina, não tentativa de acesso. Se isto quebrar, o
    # access_logs volta a ser 85% ruído e a auditoria afoga.
    cliente = porta(erro=ValueError("Nenhum rosto detectado na imagem enviada"))
    r = bater_na_porta(cliente)
    assert r.json["etapa"] == "rosto"
    assert porta.cursor.de("insert into access_logs") == []


def test_tentativa_de_burla_vira_log(porta):
    # O oposto do teste acima, e o motivo de os dois casos serem etapas
    # diferentes: foto erguida na câmera é exatamente o que o log existe
    # pra guardar.
    from services.face_service import RostoFalsoError

    cliente = porta(erro=RostoFalsoError("Isso parece uma foto"))
    bater_na_porta(cliente)
    assert len(porta.cursor.de("insert into access_logs")) == 1


def test_nada_e_gravado_pela_fila_quando_o_banco_responde(porta, tmp_path):
    bater_na_porta(porta(RECONHECIDO, EVENTO, {"id": 5}))
    assert not (tmp_path / "pendentes.jsonl").exists()


# ------------------------------------------------------------
# A invariante que sustenta o modo offline
# ------------------------------------------------------------

def test_os_dois_caminhos_respondem_igual(porta, monkeypatch, tmp_path):
    """
    Mesmo cenário, decidido pelo banco e pela cópia local: o corpo da
    resposta tem que ser idêntico. É o que garante que o totem não mude de
    comportamento no dia em que a internet cair.
    """
    online = bater_na_porta(porta(RECONHECIDO, EVENTO, {"id": 5})).json
    # Sem isto o teste passaria com os dois caminhos falhando igual, que é
    # justamente o cenário que ele deveria pegar.
    assert online["liberado"] is True

    inicio = datetime.now(timezone.utc) - timedelta(minutes=10)
    copia = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "faces": [{"usuario_id": ANA, "nome": "Ana", "embedding": vetor(1.0, 0.0)}],
        "dispositivos": [dict(DISPOSITIVO, chave_hash=CHAVE_HASH)],
        "eventos": [{
            "id": EVENTO["id"], "titulo": EVENTO["titulo"],
            "local": "Quadra", "local_norm": "quadra",
            "data_inicio": inicio.isoformat(),
            "data_fim": (inicio + timedelta(hours=1)).isoformat(),
            "participantes": [ANA],
        }],
    }
    monkeypatch.setattr(faces, "sem_banco", lambda: True)
    monkeypatch.setattr(device_auth, "sem_banco", lambda: True)
    monkeypatch.setattr(cache_local, "carregar", lambda *a, **k: copia)

    app = Flask(__name__)
    app.register_blueprint(faces.bp)
    offline = bater_na_porta(app.test_client()).json

    assert online == offline
